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
    ClaudeConfig,
    ProviderConfig,
    get_default_config,
    OPENAI_API_KEY_ENV,
    GEMINI_API_KEY_ENV,
    CLAUDE_API_KEY_ENV,
    OPENAI_API_KEY_FILE,
    GEMINI_API_KEY_FILE,
    CLAUDE_API_KEY_FILE,
)
from .exceptions import (
    MsgModelError,
    ConfigurationError,
    AuthenticationError,
    FileError,
    APIError,
)
from .providers.openai import OpenAIProvider
from .providers.gemini import GeminiProvider
from .providers.claude import ClaudeProvider

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
    """
    text: str
    raw_response: Dict[str, Any]
    model: str
    provider: str
    usage: Optional[Dict[str, int]] = None


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
        Provider.CLAUDE: CLAUDE_API_KEY_ENV,
    }
    
    key_files = {
        Provider.OPENAI: OPENAI_API_KEY_FILE,
        Provider.GEMINI: GEMINI_API_KEY_FILE,
        Provider.CLAUDE: CLAUDE_API_KEY_FILE,
    }
    
    # Try environment variable
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


def _prepare_file_data(file_path: str) -> Dict[str, Any]:
    """
    Prepare file data for API submission.
    
    Args:
        file_path: Path to the file
        
    Returns:
        Dictionary containing file metadata and encoded data
        
    Raises:
        FileError: If the file cannot be read
    """
    path = Path(file_path)
    
    if not path.exists():
        raise FileError(f"File not found: {file_path}")
    
    mime_type, _ = mimetypes.guess_type(file_path)
    if not mime_type:
        mime_type = MIME_TYPE_OCTET_STREAM
    
    try:
        with open(file_path, "rb") as f:
            binary_content = f.read()
            encoded_data = base64.b64encode(binary_content).decode("utf-8")
    except IOError as e:
        raise FileError(f"Failed to read file {file_path}: {e}")
    
    return {
        "mime_type": mime_type,
        "data": encoded_data,
        "filename": path.name,
        "path": file_path,
    }


def _prepare_file_like_data(file_like: io.BytesIO, filename: str = "upload.bin") -> Dict[str, Any]:
    """
    Prepare file-like object data for API submission.
    
    Processes a BytesIO object entirely in memory (never touches disk).
    
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
    
    # Try to guess MIME type from filename, default to octet-stream
    mime_type, _ = mimetypes.guess_type(filename)
    if not mime_type:
        mime_type = MIME_TYPE_OCTET_STREAM
    
    encoded_data = base64.b64encode(binary_content).decode("utf-8")
    
    return {
        "mime_type": mime_type,
        "data": encoded_data,
        "filename": filename,
        "is_file_like": True,  # Mark as in-memory file
    }


def _validate_max_tokens(max_tokens: int) -> None:
    """Validate max_tokens parameter."""
    if max_tokens < 1:
        raise ConfigurationError("max_tokens must be at least 1")
    if max_tokens > 1000000:
        logger.warning(f"max_tokens={max_tokens} is very large and may cause issues")


def query(
    provider: Union[str, Provider],
    prompt: str,
    api_key: Optional[str] = None,
    system_instruction: Optional[str] = None,
    file_path: Optional[str] = None,
    file_like: Optional[io.BytesIO] = None,
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
        provider: The LLM provider ('openai', 'gemini', 'claude', or 'o', 'g', 'c')
        prompt: The user prompt text
        api_key: API key (optional if set via env var or file)
        system_instruction: Optional system instruction/prompt
        file_path: Optional path to a file (image, PDF, etc.)
        file_like: Optional file-like object (io.BytesIO) - must be seekable
        config: Optional provider-specific configuration object
        max_tokens: Override for max tokens (convenience parameter)
        model: Override for model (convenience parameter)
        temperature: Override for temperature (convenience parameter)
    
    Returns:
        LLMResponse containing the text response and metadata
    
    Raises:
        ConfigurationError: For invalid configuration or file conflicts
        AuthenticationError: For API key issues
        FileError: For file-related issues
        APIError: For API call failures
    
    Examples:
        >>> # Simple query with env var API key
        >>> response = query("openai", "Hello, world!")
        >>> print(response.text)
        
        >>> # Query with file attachment from disk
        >>> response = query("gemini", "Describe this image", file_path="photo.jpg")
        
        >>> # Query with in-memory file (privacy-focused, no disk access)
        >>> import io
        >>> file_obj = io.BytesIO(binary_content)
        >>> response = query(
        ...     "openai",
        ...     "Analyze this document",
        ...     file_like=file_obj,
        ...     system_instruction="You are a document analyst"
        ... )
    """
    # Normalize provider
    if isinstance(provider, str):
        provider = Provider.from_string(provider)
    
    # Check for mutually exclusive file parameters
    if file_path is not None and file_like is not None:
        raise ConfigurationError(
            "Cannot specify both file_path and file_like. "
            "Use file_path for disk files or file_like for in-memory BytesIO objects, not both."
        )
    
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
    if file_path:
        file_data = _prepare_file_data(file_path)
    elif file_like:
        file_data = _prepare_file_like_data(file_like)
    
    # Check for unsupported providers
    if provider == Provider.CLAUDE:
        raise ConfigurationError(
            "Claude is not supported in msgmodel.\n\n"
            "REASON: Claude retains data for up to 30 days for abuse prevention.\n"
            "This is incompatible with msgmodel's zero-retention privacy requirements.\n\n"
            "ALTERNATIVES:\n"
            "  - Google Gemini (paid tier): ~24-72 hour retention for abuse monitoring only\n"
            "    • Requires Google Cloud Billing with paid API quota\n"
            "    • See: https://ai.google.dev/gemini-api/terms\n\n"
            "  - OpenAI: Zero data retention (enforced non-negotiably)\n"
            "    • See: https://platform.openai.com/docs/guides/zero-data-retention\n\n"
            "Use 'openai' or 'gemini' provider instead."
        )
    
    # Create provider instance and make request
    if provider == Provider.OPENAI:
        assert isinstance(config, OpenAIConfig)
        prov = OpenAIProvider(key, config)
        try:
            # Handle PDF upload for OpenAI
            if file_data and file_data.get("mime_type") == MIME_TYPE_PDF:
                file_id = prov.upload_file(file_data["path"])
                file_data["file_id"] = file_id
            
            raw_response = prov.query(prompt, system_instruction, file_data)
            text = prov.extract_text(raw_response)
        finally:
            prov.cleanup()
        
    elif provider == Provider.GEMINI:
        assert isinstance(config, GeminiConfig)
        prov = GeminiProvider(key, config)
        raw_response = prov.query(prompt, system_instruction, file_data)
        text = prov.extract_text(raw_response)
        
    else:  # Provider.CLAUDE
        assert isinstance(config, ClaudeConfig)
        prov = ClaudeProvider(key, config)
        raw_response = prov.query(prompt, system_instruction, file_data)
        text = prov.extract_text(raw_response)
    
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
    )


def stream(
    provider: Union[str, Provider],
    prompt: str,
    api_key: Optional[str] = None,
    system_instruction: Optional[str] = None,
    file_path: Optional[str] = None,
    file_like: Optional[io.BytesIO] = None,
    config: Optional[ProviderConfig] = None,
    max_tokens: Optional[int] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = None,
) -> Iterator[str]:
    """
    Stream a response from an LLM provider.
    
    Similar to query(), but yields text chunks as they arrive instead
    of waiting for the complete response.
    
    Args:
        provider: The LLM provider ('openai', 'gemini', 'claude', or 'o', 'g', 'c')
        prompt: The user prompt text
        api_key: API key (optional if set via env var or file)
        system_instruction: Optional system instruction/prompt
        file_path: Optional path to a file (image, PDF, etc.)
        file_like: Optional file-like object (io.BytesIO) - must be seekable
        config: Optional provider-specific configuration object
        max_tokens: Override for max tokens (convenience parameter)
        model: Override for model (convenience parameter)
        temperature: Override for temperature (convenience parameter)
    
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
        
        >>> # Stream with file attachment from disk
        >>> for chunk in stream("gemini", "Summarize this PDF", file_path="document.pdf"):
        ...     print(chunk, end="", flush=True)
        
        >>> # Stream with in-memory file (privacy-focused, no disk access)
        >>> import io
        >>> file_obj = io.BytesIO(uploaded_file_bytes)
        >>> for chunk in stream(
        ...     "openai",
        ...     "Analyze this uploaded file",
        ...     file_like=file_obj,
        ...     system_instruction="Provide detailed analysis"
        ... ):
        ...     print(chunk, end="", flush=True)
    """
    # Normalize provider
    if isinstance(provider, str):
        provider = Provider.from_string(provider)
    
    # Check for mutually exclusive file parameters
    if file_path is not None and file_like is not None:
        raise ConfigurationError(
            "Cannot specify both file_path and file_like. "
            "Use file_path for disk files or file_like for in-memory BytesIO objects, not both."
        )
    
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
    if file_path:
        file_data = _prepare_file_data(file_path)
    elif file_like:
        file_data = _prepare_file_like_data(file_like)
    
    # Check for unsupported providers
    if provider == Provider.CLAUDE:
        raise ConfigurationError(
            "Claude is not supported in msgmodel.\n\n"
            "REASON: Claude retains data for up to 30 days for abuse prevention.\n"
            "This is incompatible with msgmodel's zero-retention privacy requirements.\n\n"
            "ALTERNATIVES:\n"
            "  - Google Gemini (paid tier): ~24-72 hour retention for abuse monitoring only\n"
            "    • Requires Google Cloud Billing with paid API quota\n"
            "    • See: https://ai.google.dev/gemini-api/terms\n\n"
            "  - OpenAI: Zero data retention (enforced non-negotiably)\n"
            "    • See: https://platform.openai.com/docs/guides/zero-data-retention\n\n"
            "Use 'openai' or 'gemini' provider instead."
        )
    
    # Create provider instance and stream
    if provider == Provider.OPENAI:
        assert isinstance(config, OpenAIConfig)
        prov = OpenAIProvider(key, config)
        try:
            # Handle PDF upload for OpenAI
            if file_data and file_data.get("mime_type") == MIME_TYPE_PDF:
                file_id = prov.upload_file(file_data["path"])
                file_data["file_id"] = file_id
            
            yield from prov.stream(prompt, system_instruction, file_data)
        finally:
            prov.cleanup()
        
    elif provider == Provider.GEMINI:
        assert isinstance(config, GeminiConfig)
        prov = GeminiProvider(key, config)
        yield from prov.stream(prompt, system_instruction, file_data)
