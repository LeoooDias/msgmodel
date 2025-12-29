"""
msgmodel
~~~~~~~~

A unified Python library for interacting with LLM providers.

Supports OpenAI, Google Gemini, and Anthropic Claude with a single, consistent interface.
msgmodel itself is entirely stateless and ephemeral—it never retains your data.

Basic usage:
    >>> from msgmodel import query
    >>> response = query("openai", "Hello, world!")
    >>> print(response.text)

Streaming:
    >>> from msgmodel import stream
    >>> for chunk in stream("openai", "Tell me a story"):
    ...     print(chunk, end="", flush=True)

With custom configuration:
    >>> from msgmodel import query, OpenAIConfig
    >>> config = OpenAIConfig(model="gpt-4o-mini", temperature=0.7)
    >>> response = query("openai", "Hello!", config=config)

Async support (requires aiohttp):
    >>> import asyncio
    >>> from msgmodel import aquery, astream
    >>> 
    >>> async def main():
    ...     response = await aquery("openai", "Hello!")
    ...     async for chunk in astream("openai", "Tell me a story"):
    ...         print(chunk, end="", flush=True)
    >>> 
    >>> asyncio.run(main())
"""

__version__ = "4.1.1"
__author__ = "Leo Dias"

# Core API
from .core import query, stream, stream_panels, LLMResponse

# Configuration
from .config import (
    Provider,
    OpenAIConfig,
    GeminiConfig,
    AnthropicConfig,
    get_default_config,
)

# Alias for CLI compatibility
ClaudeConfig = AnthropicConfig

# Exceptions (v3.2.6: Enhanced with more specific types)
from .exceptions import (
    MsgModelError,
    ConfigurationError,
    ValidationError,
    AuthenticationError,
    FileError,
    APIError,
    ProviderError,
    RateLimitError,
    ContextLengthError,
    ServiceUnavailableError,
    StreamingError,
)

# Validation utilities (v3.2.6)
from .validation import (
    validate_prompt,
    validate_temperature,
    validate_max_tokens,
    validate_top_p,
    validate_api_key,
    validate_model_name,
    validate_timeout,
)

# Retry utilities (v3.2.6)
from .retry import (
    retry_on_transient_error,
    RetryConfig,
    RETRY_DEFAULT,
    RETRY_AGGRESSIVE,
    RETRY_CONSERVATIVE,
)

# Providers (for advanced usage)
from .providers import OpenAIProvider, GeminiProvider, AnthropicProvider

# Security (v3.2.1+)
from .security import RequestSigner

# Async support (v3.2.6) - lazy import to avoid requiring aiohttp
def __getattr__(name: str):
    """Lazy import for async functions to avoid requiring aiohttp."""
    if name in ("aquery", "astream", "astream_panels"):
        from .async_core import aquery, astream, astream_panels
        if name == "aquery":
            return aquery
        elif name == "astream":
            return astream
        else:
            return astream_panels
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")

__all__ = [
    # Version
    "__version__",
    # Core API
    "query",
    "stream",
    "stream_panels",
    "LLMResponse",
    # Async API (v3.2.6)
    "aquery",
    "astream",
    "astream_panels",
    # Configuration
    "Provider",
    "OpenAIConfig",
    "GeminiConfig",
    "AnthropicConfig",
    "ClaudeConfig",
    "get_default_config",
    # Exceptions
    "MsgModelError",
    "ConfigurationError",
    "ValidationError",
    "AuthenticationError",
    "FileError",
    "APIError",
    "ProviderError",
    "RateLimitError",
    "ContextLengthError",
    "ServiceUnavailableError",
    "StreamingError",
    # Validation (v3.2.6)
    "validate_prompt",
    "validate_temperature",
    "validate_max_tokens",
    "validate_top_p",
    "validate_api_key",
    "validate_model_name",
    "validate_timeout",
    # Retry (v3.2.6)
    "retry_on_transient_error",
    "RetryConfig",
    "RETRY_DEFAULT",
    "RETRY_AGGRESSIVE",
    "RETRY_CONSERVATIVE",
    # Providers
    "OpenAIProvider",
    "GeminiProvider",
    "AnthropicProvider",
    # Security
    "RequestSigner",
]
