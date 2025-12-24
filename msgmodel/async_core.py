"""
msgmodel.async_core
~~~~~~~~~~~~~~~~~~~

Async API for the msgmodel library.

Provides asynchronous versions of query() and stream() for use in
async/await code. These functions are non-blocking and can be used
in asyncio event loops.

Basic usage:
    >>> import asyncio
    >>> from msgmodel.async_core import aquery, astream
    
    >>> async def main():
    ...     response = await aquery("openai", "Hello!")
    ...     print(response.text)
    ...     
    ...     async for chunk in astream("openai", "Tell me a story"):
    ...         print(chunk, end="", flush=True)
    
    >>> asyncio.run(main())
"""

import asyncio
import io
import json
import logging
from typing import Any, AsyncIterator, Dict, Optional, Union

from .config import (
    Provider,
    OpenAIConfig,
    GeminiConfig,
    AnthropicConfig,
    ProviderConfig,
    get_default_config,
    OPENAI_URL,
    GEMINI_URL,
    ANTHROPIC_URL,
)
from .core import (
    _get_api_key,
    _prepare_file_like_data,
    _validate_max_tokens,
    LLMResponse,
)
from .exceptions import (
    ConfigurationError,
    APIError,
    StreamingError,
)

logger = logging.getLogger(__name__)

# Check for aiohttp availability
try:
    import aiohttp
    AIOHTTP_AVAILABLE = True
except ImportError:
    AIOHTTP_AVAILABLE = False


def _ensure_aiohttp() -> None:
    """Raise an error if aiohttp is not installed."""
    if not AIOHTTP_AVAILABLE:
        raise ImportError(
            "aiohttp is required for async support. "
            "Install it with: pip install msgmodel[async] or pip install aiohttp"
        )


async def aquery(
    provider: Union[str, Provider],
    prompt: str,
    api_key: Optional[str] = None,
    system_instruction: Optional[str] = None,
    file_like: Optional[io.BytesIO] = None,
    filename: Optional[str] = None,
    config: Optional[ProviderConfig] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout: float = 300,
) -> LLMResponse:
    """
    Async version of query() - query an LLM provider asynchronously.
    
    This function is non-blocking and can be used in async/await code.
    Requires the 'aiohttp' package to be installed.
    
    Args:
        provider: The LLM provider ('openai' or 'gemini', or 'o', 'g')
        prompt: The user prompt text
        api_key: API key (optional if set via env var or file)
        system_instruction: Optional system instruction/prompt
        file_like: Optional file-like object (io.BytesIO) - must be seekable
        filename: Optional filename hint for MIME type detection
        config: Optional provider-specific configuration object
        max_tokens: Override for max tokens
        model: Override for model
        temperature: Override for temperature
        timeout: Request timeout in seconds (default: 300)
    
    Returns:
        LLMResponse containing the text response and metadata
    
    Raises:
        ImportError: If aiohttp is not installed
        ConfigurationError: For invalid configuration
        AuthenticationError: For API key issues
        FileError: For file-related issues
        APIError: For API call failures
    
    Example:
        >>> import asyncio
        >>> from msgmodel.async_core import aquery
        >>> 
        >>> async def main():
        ...     response = await aquery("openai", "Hello!")
        ...     print(response.text)
        >>> 
        >>> asyncio.run(main())
    """
    _ensure_aiohttp()
    
    # Normalize provider
    if isinstance(provider, str):
        provider = Provider.from_string(provider)
    
    # Get API key
    key = _get_api_key(provider, api_key)
    
    # Get or create config
    if config is None:
        config = get_default_config(provider)
    
    # Apply convenience overrides
    if max_tokens is not None:
        _validate_max_tokens(max_tokens)
        config.max_tokens = max_tokens
    if model is not None:
        config.model = model
    if temperature is not None:
        config.temperature = temperature
    
    # Prepare file data if provided
    file_data = None
    if file_like:
        file_hint = filename or getattr(file_like, 'name', 'upload.bin')
        file_data = _prepare_file_like_data(file_like, filename=file_hint)
    
    # Make async request based on provider
    if provider == Provider.OPENAI:
        return await _aquery_openai(key, prompt, system_instruction, file_data, config, timeout)
    elif provider == Provider.GEMINI:
        return await _aquery_gemini(key, prompt, system_instruction, file_data, config, timeout)
    else:
        raise ConfigurationError(f"Unsupported provider: {provider}")


async def _aquery_openai(
    api_key: str,
    prompt: str,
    system_instruction: Optional[str],
    file_data: Optional[Dict[str, Any]],
    config: OpenAIConfig,
    timeout: float,
) -> LLMResponse:
    """Make async query to OpenAI."""
    from .providers.openai import OpenAIProvider
    
    # Build payload using the sync provider's method
    prov = OpenAIProvider(api_key, config)
    payload = prov._build_payload(prompt, system_instruction, file_data)
    headers = prov._build_headers()
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            OPENAI_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            if not response.ok:
                text = await response.text()
                raise APIError(
                    f"OpenAI API error: {text}",
                    status_code=response.status,
                    response_text=text,
                    provider="openai",
                )
            
            raw_response = await response.json()
    
    text = prov.extract_text(raw_response)
    usage = raw_response.get("usage")
    privacy_metadata = OpenAIProvider.get_privacy_info()
    
    return LLMResponse(
        text=text,
        raw_response=raw_response,
        model=config.model,
        provider="openai",
        usage=usage,
        privacy=privacy_metadata,
    )


# Module-level cache for verified Gemini API keys (privacy-critical)
_verified_gemini_keys: set = set()


def _verify_gemini_billing_sync(api_key: str, config: GeminiConfig) -> None:
    """
    Synchronously verify Gemini billing status.
    
    PRIVACY CRITICAL: This ensures we only use paid Gemini API which does NOT
    retain prompts for training. Unpaid API retains ALL data for model training.
    
    Results are cached per API key to avoid repeated verification calls.
    """
    global _verified_gemini_keys
    
    if api_key in _verified_gemini_keys:
        return  # Already verified in this session
    
    from .providers.gemini import GeminiProvider
    # This will raise ConfigurationError if billing check fails
    _ = GeminiProvider(api_key, config)
    _verified_gemini_keys.add(api_key)


async def _aquery_gemini(
    api_key: str,
    prompt: str,
    system_instruction: Optional[str],
    file_data: Optional[Dict[str, Any]],
    config: GeminiConfig,
    timeout: float,
) -> LLMResponse:
    """Make async query to Gemini."""
    from .providers.gemini import GeminiProvider
    
    # PRIVACY CRITICAL: Verify paid API access before making any request
    # This runs synchronously but is cached, so only the first call blocks
    await asyncio.get_event_loop().run_in_executor(
        None, _verify_gemini_billing_sync, api_key, config
    )
    
    # Build payload using the sync provider's method (now safe - billing verified)
    prov = GeminiProvider.create_with_cached_validation(api_key, config, verified=True)
    
    url = prov._build_url()
    payload = prov._build_payload(prompt, system_instruction, file_data)
    headers = {"Content-Type": "application/json"}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            if not response.ok:
                text = await response.text()
                raise APIError(
                    f"Gemini API error: {text}",
                    status_code=response.status,
                    response_text=text,
                    provider="gemini",
                )
            
            raw_response = await response.json()
    
    text = prov.extract_text(raw_response)
    usage = raw_response.get("usage")
    privacy_metadata = GeminiProvider.get_privacy_info()
    
    return LLMResponse(
        text=text,
        raw_response=raw_response,
        model=config.model,
        provider="gemini",
        usage=usage,
        privacy=privacy_metadata,
    )


async def astream(
    provider: Union[str, Provider],
    prompt: str,
    api_key: Optional[str] = None,
    system_instruction: Optional[str] = None,
    file_like: Optional[io.BytesIO] = None,
    filename: Optional[str] = None,
    config: Optional[ProviderConfig] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
    timeout: float = 300,
) -> AsyncIterator[str]:
    """
    Async version of stream() - stream responses asynchronously.
    
    This function is non-blocking and yields text chunks as they arrive.
    Requires the 'aiohttp' package to be installed.
    
    Args:
        provider: The LLM provider ('openai' or 'gemini', or 'o', 'g')
        prompt: The user prompt text
        api_key: API key (optional if set via env var or file)
        system_instruction: Optional system instruction/prompt
        file_like: Optional file-like object (io.BytesIO)
        filename: Optional filename hint for MIME type detection
        config: Optional provider-specific configuration object
        max_tokens: Override for max tokens
        model: Override for model
        temperature: Override for temperature
        timeout: Request timeout in seconds (default: 300)
    
    Yields:
        Text chunks as they arrive from the API
    
    Raises:
        ImportError: If aiohttp is not installed
        ConfigurationError: For invalid configuration
        AuthenticationError: For API key issues
        FileError: For file-related issues
        APIError: For API call failures
        StreamingError: For streaming-specific issues
    
    Example:
        >>> import asyncio
        >>> from msgmodel.async_core import astream
        >>> 
        >>> async def main():
        ...     async for chunk in astream("openai", "Tell me a story"):
        ...         print(chunk, end="", flush=True)
        >>> 
        >>> asyncio.run(main())
    """
    _ensure_aiohttp()
    
    # Normalize provider
    if isinstance(provider, str):
        provider = Provider.from_string(provider)
    
    # Get API key
    key = _get_api_key(provider, api_key)
    
    # Get or create config
    if config is None:
        config = get_default_config(provider)
    
    # Apply convenience overrides
    if max_tokens is not None:
        _validate_max_tokens(max_tokens)
        config.max_tokens = max_tokens
    if model is not None:
        config.model = model
    if temperature is not None:
        config.temperature = temperature
    
    # Prepare file data if provided
    file_data = None
    if file_like:
        file_hint = filename or getattr(file_like, 'name', 'upload.bin')
        file_data = _prepare_file_like_data(file_like, filename=file_hint)
    
    # Stream based on provider
    if provider == Provider.OPENAI:
        async for chunk in _astream_openai(key, prompt, system_instruction, file_data, config, timeout):
            yield chunk
    elif provider == Provider.GEMINI:
        async for chunk in _astream_gemini(key, prompt, system_instruction, file_data, config, timeout):
            yield chunk
    else:
        raise ConfigurationError(f"Unsupported provider: {provider}")


async def _astream_openai(
    api_key: str,
    prompt: str,
    system_instruction: Optional[str],
    file_data: Optional[Dict[str, Any]],
    config: OpenAIConfig,
    timeout: float,
) -> AsyncIterator[str]:
    """Make async streaming request to OpenAI."""
    from .providers.openai import OpenAIProvider
    
    prov = OpenAIProvider(api_key, config)
    payload = prov._build_payload(prompt, system_instruction, file_data, stream=True)
    headers = prov._build_headers()
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            OPENAI_URL,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            if not response.ok:
                text = await response.text()
                raise APIError(
                    f"OpenAI API error: {text}",
                    status_code=response.status,
                    response_text=text,
                    provider="openai",
                )
            
            async for line in response.content:
                line_text = line.decode("utf-8").strip()
                if line_text.startswith("data: "):
                    data = line_text[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        if "choices" in chunk:
                            for choice in chunk["choices"]:
                                delta = choice.get("delta", {})
                                text = delta.get("content", "")
                                if text:
                                    yield text
                    except json.JSONDecodeError:
                        continue


async def _astream_gemini(
    api_key: str,
    prompt: str,
    system_instruction: Optional[str],
    file_data: Optional[Dict[str, Any]],
    config: GeminiConfig,
    timeout: float,
) -> AsyncIterator[str]:
    """Make async streaming request to Gemini."""
    from .providers.gemini import GeminiProvider
    
    # PRIVACY CRITICAL: Verify paid API access before making any request
    await asyncio.get_event_loop().run_in_executor(
        None, _verify_gemini_billing_sync, api_key, config
    )
    
    # Create provider with cached verification (now safe - billing verified)
    prov = GeminiProvider.create_with_cached_validation(api_key, config, verified=True)
    
    url = prov._build_url(stream=True)
    payload = prov._build_payload(prompt, system_instruction, file_data)
    headers = {"Content-Type": "application/json"}
    
    async with aiohttp.ClientSession() as session:
        async with session.post(
            url,
            json=payload,
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=timeout),
        ) as response:
            if not response.ok:
                text = await response.text()
                raise APIError(
                    f"Gemini API error: {text}",
                    status_code=response.status,
                    response_text=text,
                    provider="gemini",
                )
            
            async for line in response.content:
                line_text = line.decode("utf-8").strip()
                if line_text.startswith("data: "):
                    data = line_text[6:]
                    try:
                        chunk = json.loads(data)
                        text = prov.extract_text(chunk)
                        if text:
                            yield text
                    except json.JSONDecodeError:
                        continue
