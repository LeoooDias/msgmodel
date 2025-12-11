"""
msgmodel.exceptions
~~~~~~~~~~~~~~~~~~~

Custom exceptions for the msgmodel library.

All exceptions inherit from MsgModelError, allowing callers to catch
all library-specific errors with a single except clause.
"""


class MsgModelError(Exception):
    """Base exception for all msgmodel errors."""
    pass


class ConfigurationError(MsgModelError):
    """
    Raised when configuration is invalid or incomplete.
    
    Examples:
        - Invalid provider name
        - Invalid max_tokens value
        - Missing required parameters
    """
    pass


class AuthenticationError(MsgModelError):
    """
    Raised when API authentication fails.
    
    Examples:
        - Missing API key
        - Invalid API key
        - API key file not found
    """
    pass


class FileError(MsgModelError):
    """
    Raised when file operations fail.
    
    Examples:
        - File not found
        - Unable to read file
        - Invalid file format
    """
    pass


class APIError(MsgModelError):
    """
    Raised when an API call fails.
    
    Attributes:
        status_code: HTTP status code from the API response
        response_text: Raw response text from the API
    """
    
    def __init__(
        self,
        message: str,
        status_code: int | None = None,
        response_text: str | None = None
    ):
        super().__init__(message)
        self.status_code = status_code
        self.response_text = response_text


class ProviderError(MsgModelError):
    """
    Raised when a provider-specific error occurs.
    
    Examples:
        - Unsupported file type for provider
        - Provider-specific validation failure
        - Missing provider dependency (e.g., anthropic package)
    """
    pass


class StreamingError(MsgModelError):
    """
    Raised when streaming-specific errors occur.
    
    Examples:
        - Connection interrupted during streaming
        - Invalid streaming response format
    """
    pass
