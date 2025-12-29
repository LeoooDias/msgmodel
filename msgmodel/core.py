"""
msgmodel.core
~~~~~~~~~~~~~

Core API for the msgmodel library.

Provides a unified interface to query any supported LLM provider.
"""

import os
import io
import base64
import mimetypes
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Iterator, Union

from .config import (
    Provider,
    OpenAIConfig,
    GeminiConfig,
    AnthropicConfig,
    ProviderConfig,
    get_default_config,
    OPENAI_API_KEY_ENV,
    GEMINI_API_KEY_ENV,
    ANTHROPIC_API_KEY_ENV,
    OPENAI_API_KEY_FILE,
    GEMINI_API_KEY_FILE,
    ANTHROPIC_API_KEY_FILE,
)
from .exceptions import (
    MsgModelError,
    ConfigurationError,
    AuthenticationError,
    FileError,
    APIError,
    StreamingError,
)
from .providers.openai import OpenAIProvider
from .providers.gemini import GeminiProvider
from .providers.anthropic import AnthropicProvider

logger = logging.getLogger(__name__)

# MIME type constants
MIME_TYPE_PDF = "application/pdf"
MIME_TYPE_OCTET_STREAM = "application/octet-stream"
FILE_ENCODING = "utf-8"


@dataclass
class LLMResponse:
    """
    Structured response from an LLM provider.
    
    Attributes:
        text: The extracted text response
        raw_response: The complete raw API response
        model: The model that generated the response
        provider: The provider that was used
        usage: Token usage information (if available)
        privacy: Data handling information for this specific interaction
    
    Note: The __repr__ and __str__ methods redact response content to prevent
    accidental logging of potentially sensitive data. Access .text or
    .raw_response directly when you need the actual content.
    
    The `privacy` field contains metadata about how this specific request
    was handled regarding data retention by the provider.
    
    Note: msgmodel itself never retains data—each request is stateless and ephemeral.
    """
    text: str
    raw_response: Dict[str, Any]
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None
    privacy: Optional[Dict[str, Any]] = None
    
    def __repr__(self) -> str:
        """Privacy-safe representation that redacts response content."""
        text_preview = f"{len(self.text)} chars" if self.text else "empty"
        return (
            f"LLMResponse(text=[REDACTED: {text_preview}], "
            f"raw_response=[REDACTED], model={self.model!r}, "
            f"provider={self.provider!r}, usage={self.usage}, privacy={self.privacy})"
        )
    
    def __str__(self) -> str:
        """Privacy-safe string representation."""
        return self.__repr__()


def _get_api_key(
    provider: Provider,
    api_key: Optional[str] = None
) -> str:
    """
    Get the API key for a provider from various sources.
    
    Priority:
    1. Directly provided api_key parameter
    2. Environment variable
    3. Key file in current directory
    
    Args:
        provider: The LLM provider
        api_key: Optional directly provided API key
        
    Returns:
        The API key string
        
    Raises:
        AuthenticationError: If no API key can be found
    """
    if api_key:
        return api_key
    
    # Map providers to their env vars and files
    env_vars = {
        Provider.OPENAI: OPENAI_API_KEY_ENV,
        Provider.GEMINI: GEMINI_API_KEY_ENV,
        Provider.ANTHROPIC: ANTHROPIC_API_KEY_ENV,
    }
    
    key_files = {
        Provider.OPENAI: OPENAI_API_KEY_FILE,
        Provider.GEMINI: GEMINI_API_KEY_FILE,
        Provider.ANTHROPIC: ANTHROPIC_API_KEY_FILE,
    }
    
    env_var = env_vars[provider]
    key = os.environ.get(env_var)
    if key:
        return key
    
    # Try key file
    key_file = key_files[provider]
    if Path(key_file).exists():
        try:
            with open(key_file, "r", encoding=FILE_ENCODING) as f:
                return f.read().strip()
        except IOError as e:
            raise AuthenticationError(f"Failed to read API key file {key_file}: {e}")
    
    raise AuthenticationError(
        f"No API key found for {provider.value}. "
        f"Provide api_key parameter, set {env_var} environment variable, "
        f"or create {key_file} file."
    )


def _infer_mime_type(file_like: io.BytesIO, filename: Optional[str] = None) -> str:
    """
    Infer MIME type from filename or file content with fallback magic byte detection.
    
    v3.2.1 Enhancement: Detects MIME type using multiple strategies:
    1. Filename-based detection (fastest, most reliable)
    2. Magic byte detection (fallback for files without extensions)
    3. Safe default (application/octet-stream)
    
    Args:
        file_like: BytesIO object to inspect
        filename: Optional filename hint for MIME type detection
        
    Returns:
        MIME type string (e.g., 'image/png', 'application/pdf')
    """
    # Strategy 1: Try filename-based detection
    if filename:
        mime_type, _ = mimetypes.guess_type(filename)
        if mime_type:
            return mime_type
    
    # Strategy 2: Magic byte detection for common file formats
    try:
        current_pos = file_like.tell()
        file_like.seek(0)
        magic_bytes = file_like.read(512)
        file_like.seek(current_pos)
        
        # Magic byte signatures for common formats
        signatures = {
            b'%PDF': 'application/pdf',
            b'\x89PNG\r\n\x1a\n': 'image/png',
            b'\xff\xd8\xff': 'image/jpeg',
            b'GIF8': 'image/gif',
            b'BM': 'image/bmp',
            b'RIFF': 'audio/wav',
            b'ID3': 'audio/mpeg',
            b'PK\x03\x04': 'application/zip',
            b'\x50\x4b\x03\x04': 'application/zip',
            b'\xef\xbb\xbf<?xml': 'application/xml',
            b'<?xml': 'application/xml',
        }
        
        for sig, mime_type in signatures.items():
            if magic_bytes.startswith(sig):
                return mime_type
    except (AttributeError, IOError):
        pass
    
    # Strategy 3: Safe default
    return MIME_TYPE_OCTET_STREAM


def _prepare_file_data(file_path: str) -> Dict[str, Any]:
    """
    Prepare file data from disk for API submission.
    
    Args:
        file_path: Path to the file on disk
        
    Returns:
        Dictionary containing file metadata and encoded data
        
    Raises:
        FileError: If the file cannot be read
    """
    try:
        path = Path(file_path)
        with open(path, "rb") as f:
            binary_content = f.read()
    except (FileNotFoundError, IOError, OSError) as e:
        raise FileError(f"Failed to read file {file_path}: {e}")
    
    # Use improved MIME type inference with fallback
    mime_type = _infer_mime_type(io.BytesIO(binary_content), filename=Path(file_path).name)
    
    encoded_data = base64.b64encode(binary_content).decode("utf-8")
    
    return {
        "mime_type": mime_type,
        "data": encoded_data,
        "filename": Path(file_path).name,
        "is_file_like": False,  # Mark as disk file
    }


def _prepare_file_like_data(file_like: io.BytesIO, filename: Optional[str] = None) -> Dict[str, Any]:
    """
    Prepare file-like object data for API submission.
    
    Processes a BytesIO object entirely in memory (never touches disk).
    This provides stateless operation where each request is independent.
    
    Args:
        file_like: An io.BytesIO object containing binary data
        filename: Optional filename hint (defaults to 'upload.bin')
        
    Returns:
        Dictionary containing file metadata and encoded data
        
    Raises:
        FileError: If the file-like object cannot be read
    """
    try:
        # Seek to beginning to ensure we read the full content
        file_like.seek(0)
        binary_content = file_like.read()
        # Reset position for potential reuse by caller
        file_like.seek(0)
    except (AttributeError, IOError, OSError) as e:
        raise FileError(f"Failed to read from file-like object: {e}")
    
    # v3.2.1: Use improved MIME type inference with fallback
    mime_type = _infer_mime_type(file_like, filename)
    
    encoded_data = base64.b64encode(binary_content).decode("utf-8")
    
    return {
        "mime_type": mime_type,
        "data": encoded_data,
        "filename": filename or "upload.bin",
        "is_file_like": True,  # Mark as in-memory file
    }


def _validate_max_tokens(max_tokens: int) -> None:
    """Validate max_tokens parameter."""
    if max_tokens < 1:
        raise ConfigurationError("max_tokens must be at least 1", key_name="max_tokens")
    if max_tokens > 1000000:
        logger.warning(
            "max_tokens=%d is very large and may cause issues",
            max_tokens,
            extra={"max_tokens": max_tokens, "warning_type": "large_value"}
        )


def query(
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
) -> LLMResponse:
    """
    Query an LLM provider and return a structured response.
    
    This is the main entry point for the library. It provides a unified
    interface to all supported LLM providers.
    
    Args:
        provider: The LLM provider ('openai', 'gemini', 'anthropic', or 'o', 'g', 'a')
        prompt: The user prompt text
        api_key: API key (optional if set via env var or file)
        system_instruction: Optional system instruction/prompt
        file_like: Optional file-like object (io.BytesIO) - must be seekable
            This is the only method for file upload. Files are base64-encoded
            and embedded in prompts for privacy and stateless operation.
            Limited to practical API constraints (~15-20MB for OpenAI, ~22MB for Gemini/Anthropic).
        filename: Optional filename hint for MIME type detection when using file_like.
            If not provided, attempts to use file_like.name attribute. Defaults to 'upload.bin'
        config: Optional provider-specific configuration object
        max_tokens: Override for max tokens (convenience parameter)
        model: Override for model (convenience parameter)
        temperature: Override for temperature (convenience parameter)
    
    Returns:
        LLMResponse containing the text response, metadata, and privacy information.
        The `privacy` field contains details about data handling for this specific request.
    
    Raises:
        ConfigurationError: For invalid configuration
        AuthenticationError: For API key issues
        FileError: For file-related issues
        APIError: For API call failures
    
    Examples:
        >>> # Simple query with env var API key
        >>> response = query("openai", "Hello, world!")
        >>> print(response.text)
        >>> print(response.privacy)  # Review privacy information for this request
        
        >>> # Query with in-memory file (privacy-focused, no disk access)
        >>> import io
        >>> file_obj = io.BytesIO(binary_content)
        >>> response = query(
        ...     "anthropic",
        ...     "Analyze this document",
        ...     file_like=file_obj,
        ...     filename="document.pdf",  # Enables proper MIME type detection
        ...     system_instruction="You are a document analyst"
        ... )
        
        >>> # Using .name attribute on BytesIO (alternative to filename param)
        >>> file_obj = io.BytesIO(binary_content)
        >>> file_obj.name = "image.png"  # Set name attribute for MIME detection
        >>> response = query("gemini", "Describe this image", file_like=file_obj)
    """
    # Normalize provider
    if isinstance(provider, str):
        provider = Provider.from_string(provider)
    
    # Get or create config
    if config is None:
        config = get_default_config(provider)
    
    # Get API key: prioritize explicit api_key param, then config.api_key, then env/file
    config_api_key = getattr(config, 'api_key', None)
    key = _get_api_key(provider, api_key or config_api_key)
    
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
        # Use provided filename, fall back to .name attribute, then default
        file_hint = filename or getattr(file_like, 'name', 'upload.bin')
        file_data = _prepare_file_like_data(file_like, filename=file_hint)
    
    # Create provider instance and make request
    privacy_metadata = None
    if provider == Provider.OPENAI:
        assert isinstance(config, OpenAIConfig)
        prov = OpenAIProvider(key, config)
        raw_response = prov.query(prompt, system_instruction, file_data)
        text = prov.extract_text(raw_response)
        privacy_metadata = prov.get_privacy_info()
        
    elif provider == Provider.GEMINI:
        assert isinstance(config, GeminiConfig)
        prov = GeminiProvider(key, config)
        raw_response = prov.query(prompt, system_instruction, file_data)
        text = prov.extract_text(raw_response)
        privacy_metadata = prov.get_privacy_info()
    
    elif provider == Provider.ANTHROPIC:
        assert isinstance(config, AnthropicConfig)
        prov = AnthropicProvider(key, config)
        raw_response = prov.query(prompt, system_instruction, file_data)
        text = prov.extract_text(raw_response)
        privacy_metadata = prov.get_privacy_info()
    
    else:
        # Should never reach here due to Provider enum, but maintain type safety
        raise ConfigurationError(f"Unsupported provider: {provider}")  # pragma: no cover
    
    # Extract usage info if available
    usage = None
    if "usage" in raw_response:
        usage = raw_response["usage"]
    
    return LLMResponse(
        text=text,
        raw_response=raw_response,
        model=config.model,
        provider=provider.value,
        usage=usage,
        privacy=privacy_metadata,
    )


def stream(
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
    on_chunk: Optional[Any] = None,
) -> Iterator[str]:
    """
    Stream a response from an LLM provider.
    
    Similar to query(), but yields text chunks as they arrive instead
    of waiting for the complete response.
    
    Args:
        provider: The LLM provider ('openai', 'gemini', 'anthropic', or 'o', 'g', 'a')
        prompt: The user prompt text
        api_key: API key (optional if set via env var or file)
        system_instruction: Optional system instruction/prompt
        file_like: Optional file-like object (io.BytesIO) - must be seekable.
            This is the only method for file upload. Files are base64-encoded
            and embedded in prompts for privacy and stateless operation.
        filename: Optional filename hint for MIME type detection when using file_like.
            If not provided, attempts to use file_like.name attribute. Defaults to 'upload.bin'
        config: Optional provider-specific configuration object
        max_tokens: Override for max tokens (convenience parameter)
        model: Override for model (convenience parameter)
        temperature: Override for temperature (convenience parameter)
        timeout: Timeout in seconds for streaming connection (default: 300s/5min). v3.2.1+
        on_chunk: Optional callback(chunk) -> bool. Return False to abort stream. v3.2.1+
    
    Yields:
        Text chunks as they arrive from the API
    
    Raises:
        ConfigurationError: For invalid configuration or file conflicts
        AuthenticationError: For API key issues
        FileError: For file-related issues
        APIError: For API call failures
        StreamingError: For streaming-specific issues
    
    Examples:
        >>> # Stream response to prompt
        >>> for chunk in stream("openai", "Tell me a story"):
        ...     print(chunk, end="", flush=True)
        
        >>> # Stream with in-memory file (privacy-focused, no disk access)
        >>> import io
        >>> file_obj = io.BytesIO(uploaded_file_bytes)
        >>> for chunk in stream(
        ...     "anthropic",
        ...     "Analyze this uploaded file",
        ...     file_like=file_obj,
        ...     filename="document.pdf",  # Enables proper MIME type detection
        ...     system_instruction="Provide detailed analysis"
        ... ):
        ...     print(chunk, end="", flush=True)
        
        >>> # Gemini with BytesIO and .name attribute for MIME detection
        >>> file_obj = io.BytesIO(image_bytes)
        >>> file_obj.name = "photo.jpg"
        >>> for chunk in stream("gemini", "Describe this photo", file_like=file_obj):
        ...     print(chunk, end="", flush=True)
    """
    # Normalize provider
    if isinstance(provider, str):
        provider = Provider.from_string(provider)
    
    # Get or create config
    if config is None:
        config = get_default_config(provider)
    
    # Get API key: prioritize explicit api_key param, then config.api_key, then env/file
    config_api_key = getattr(config, 'api_key', None)
    key = _get_api_key(provider, api_key or config_api_key)
    
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
        # Use provided filename, fall back to .name attribute, then default
        file_hint = filename or getattr(file_like, 'name', 'upload.bin')
        file_data = _prepare_file_like_data(file_like, filename=file_hint)
    
    # Create provider instance and stream
    if provider == Provider.OPENAI:
        assert isinstance(config, OpenAIConfig)
        prov = OpenAIProvider(key, config)
        yield from prov.stream(prompt, system_instruction, file_data, timeout=timeout, on_chunk=on_chunk)
        
    elif provider == Provider.GEMINI:
        assert isinstance(config, GeminiConfig)
        prov = GeminiProvider(key, config)
        yield from prov.stream(prompt, system_instruction, file_data, timeout=timeout, on_chunk=on_chunk)
    
    elif provider == Provider.ANTHROPIC:
        assert isinstance(config, AnthropicConfig)
        prov = AnthropicProvider(key, config)
        yield from prov.stream(prompt, system_instruction, file_data, timeout=timeout, on_chunk=on_chunk)
    
    else:
        # Should never reach here due to Provider enum, but maintain type safety
        raise ConfigurationError(f"Unsupported provider: {provider}")  # pragma: no cover


def stream_panels(
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
    panel_id: Optional[str] = None,
) -> Iterator[Dict[str, Any]]:
    """
    Stream a response from an LLM provider with structured panel events.
    
    This function yields structured events suitable for building chat UIs.
    Events include text deltas, final content with metadata, and the
    finish_reason for detecting truncation.
    
    Args:
        provider: The LLM provider ('openai', 'gemini', 'anthropic', or 'o', 'g', 'a')
        prompt: The user prompt text
        api_key: API key (optional if set via env var or file)
        system_instruction: Optional system instruction/prompt
        file_like: Optional file-like object (io.BytesIO) - must be seekable.
        filename: Optional filename hint for MIME type detection when using file_like.
        config: Optional provider-specific configuration object
        max_tokens: Override for max tokens (convenience parameter)
        model: Override for model (convenience parameter)
        temperature: Override for temperature (convenience parameter)
        timeout: Timeout in seconds for streaming connection (default: 300s/5min)
        panel_id: Optional identifier for this panel (auto-generated if not provided)
    
    Yields:
        Event dictionaries with the following structures:
        
        panel_delta event (text chunk):
            {
                "event": "panel_delta",
                "panel_id": str,
                "delta": str  # The text chunk
            }
        
        panel_final event (stream complete):
            {
                "event": "panel_final",
                "panel_id": str,
                "content": str,  # Full accumulated response text
                "privacy": dict,  # Privacy metadata from provider
                "finish_reason": str | None  # Raw provider finish reason
            }
        
        panel_error event (error occurred):
            {
                "event": "panel_error",
                "panel_id": str,
                "error": str,
                "error_type": str
            }
    
    Finish Reason Values by Provider:
        - OpenAI: "stop", "length", "content_filter", "tool_calls"
        - Anthropic: "end_turn", "max_tokens", "stop_sequence"
        - Gemini: "STOP", "MAX_TOKENS", "SAFETY", "RECITATION", "OTHER"
        
        Truncation indicators (response cut off due to token limit):
        - OpenAI: "length"
        - Anthropic: "max_tokens"
        - Gemini: "MAX_TOKENS"
    
    Raises:
        ConfigurationError: For invalid configuration
        AuthenticationError: For API key issues
        FileError: For file-related issues
    
    Note:
        API errors during streaming are yielded as panel_error events
        rather than raised as exceptions.
    
    Examples:
        >>> # Stream with panel events
        >>> for event in stream_panels("openai", "Tell me a story", max_tokens=50):
        ...     if event["event"] == "panel_delta":
        ...         print(event["delta"], end="", flush=True)
        ...     elif event["event"] == "panel_final":
        ...         if event["finish_reason"] == "length":
        ...             print("\\n[Response truncated due to max_tokens]")
        ...         print(f"\\nFinish reason: {event['finish_reason']}")
        
        >>> # Check for truncation
        >>> events = list(stream_panels("anthropic", "Write a long essay", max_tokens=100))
        >>> final = next(e for e in events if e["event"] == "panel_final")
        >>> if final["finish_reason"] == "max_tokens":
        ...     print("Warning: Response was truncated!")
    """
    import uuid
    
    # Generate panel_id if not provided
    if panel_id is None:
        panel_id = str(uuid.uuid4())[:8]
    
    # Normalize provider
    if isinstance(provider, str):
        provider = Provider.from_string(provider)
    
    # Get or create config
    if config is None:
        config = get_default_config(provider)
    
    # Get API key: prioritize explicit api_key param, then config.api_key, then env/file
    config_api_key = getattr(config, 'api_key', None)
    key = _get_api_key(provider, api_key or config_api_key)
    
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
    
    # Accumulate content for panel_final
    accumulated_content = []
    privacy_metadata = None
    finish_reason = None
    
    try:
        # Create provider instance and stream with finish_reason
        if provider == Provider.OPENAI:
            assert isinstance(config, OpenAIConfig)
            prov = OpenAIProvider(key, config)
            privacy_metadata = prov.get_privacy_info()
            
            for event in prov.stream_with_finish_reason(prompt, system_instruction, file_data, timeout=timeout):
                if event["type"] == "delta":
                    accumulated_content.append(event["text"])
                    yield {
                        "event": "panel_delta",
                        "panel_id": panel_id,
                        "delta": event["text"]
                    }
                elif event["type"] == "finish":
                    finish_reason = event.get("finish_reason")
                    
        elif provider == Provider.GEMINI:
            assert isinstance(config, GeminiConfig)
            prov = GeminiProvider(key, config)
            privacy_metadata = prov.get_privacy_info()
            
            for event in prov.stream_with_finish_reason(prompt, system_instruction, file_data, timeout=timeout):
                if event["type"] == "delta":
                    accumulated_content.append(event["text"])
                    yield {
                        "event": "panel_delta",
                        "panel_id": panel_id,
                        "delta": event["text"]
                    }
                elif event["type"] == "finish":
                    finish_reason = event.get("finish_reason")
        
        elif provider == Provider.ANTHROPIC:
            assert isinstance(config, AnthropicConfig)
            prov = AnthropicProvider(key, config)
            privacy_metadata = prov.get_privacy_info()
            
            for event in prov.stream_with_finish_reason(prompt, system_instruction, file_data, timeout=timeout):
                if event["type"] == "delta":
                    accumulated_content.append(event["text"])
                    yield {
                        "event": "panel_delta",
                        "panel_id": panel_id,
                        "delta": event["text"]
                    }
                elif event["type"] == "finish":
                    finish_reason = event.get("finish_reason")
        
        else:
            raise ConfigurationError(f"Unsupported provider: {provider}")
        
        # Yield final panel event with finish_reason
        yield {
            "event": "panel_final",
            "panel_id": panel_id,
            "content": "".join(accumulated_content),
            "privacy": privacy_metadata,
            "finish_reason": finish_reason
        }
        
    except (APIError, StreamingError) as e:
        yield {
            "event": "panel_error",
            "panel_id": panel_id,
            "error": str(e),
            "error_type": type(e).__name__
        }
    except Exception as e:
        yield {
            "event": "panel_error",
            "panel_id": panel_id,
            "error": str(e),
            "error_type": type(e).__name__
        }
