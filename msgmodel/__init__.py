"""
msgmodel
~~~~~~~~

A unified Python library for interacting with LLM providers.

Supports OpenAI and Google Gemini with a single, consistent interface.

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
"""

__version__ = "3.2.2"
__author__ = "Leo Dias"

# Core API
from .core import query, stream, LLMResponse

# Configuration
from .config import (
    Provider,
    OpenAIConfig,
    GeminiConfig,
    get_default_config,
)

# Exceptions
from .exceptions import (
    MsgModelError,
    ConfigurationError,
    AuthenticationError,
    FileError,
    APIError,
    ProviderError,
    StreamingError,
)

# Providers (for advanced usage)
from .providers import OpenAIProvider, GeminiProvider

# Security (v3.2.1+)
from .security import RequestSigner

__all__ = [
    # Version
    "__version__",
    # Core API
    "query",
    "stream",
    "LLMResponse",
    # Configuration
    "Provider",
    "OpenAIConfig",
    "GeminiConfig",
    "get_default_config",
    # Exceptions
    "MsgModelError",
    "ConfigurationError",
    "AuthenticationError",
    "FileError",
    "APIError",
    "ProviderError",
    "StreamingError",
    # Providers
    "OpenAIProvider",
    "GeminiProvider",
    # Security
    "RequestSigner",
]
