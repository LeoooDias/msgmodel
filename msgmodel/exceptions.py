"""
msgmodel.exceptions
~~~~~~~~~~~~~~~~~~~

Custom exceptions for the msgmodel library.

All exceptions inherit from MsgModelError, allowing callers to catch
all library-specific errors with a single except clause.

Exception Hierarchy (v3.3.0+):
    MsgModelError (base)
    ├── ConfigurationError - Setup/config issues
    ├── ValidationError - Input validation failures  
    ├── AuthenticationError - API key issues
    ├── FileError - File operation failures
    ├── APIError - General API failures
    │   └── ProviderError - Provider-specific errors
    │       ├── RateLimitError - Rate limit exceeded (429)
    │       ├── ContextLengthError - Prompt too long (400)
    │       └── ServiceUnavailableError - Temporary outage (503)
    └── StreamingError - Streaming-specific issues
"""

from typing import Optional


class MsgModelError(Exception):
    """
    Base exception for all msgmodel errors.
    
    Attributes:
        message: Human-readable error description
        cause: Optional underlying exception that caused this error
    """
    
    def __init__(self, message: str, *, cause: Optional[Exception] = None):
        super().__init__(message)
        self.message = message
        if cause is not None:
            self.__cause__ = cause
    
    def __str__(self) -> str:
        if self.__cause__:
            return f"{self.message} (caused by: {self.__cause__})"
        return self.message


class ConfigurationError(MsgModelError):
    """
    Raised when configuration is invalid or incomplete.
    
    Attributes:
        key_name: Optional name of the configuration key that caused the error
    
    Examples:
        - Invalid provider name
        - Invalid max_tokens value
        - Missing required parameters
    """
    
    def __init__(
        self,
        message: str,
        *,
        key_name: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, cause=cause)
        self.key_name = key_name


class ValidationError(MsgModelError):
    """
    Raised when input validation fails.
    
    Attributes:
        field: Optional name of the field that failed validation
    
    Examples:
        - Empty prompt
        - Invalid temperature range
        - Malformed input data
    """
    
    def __init__(
        self,
        message: str,
        *,
        field: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, cause=cause)
        self.field = field


class AuthenticationError(MsgModelError):
    """
    Raised when API authentication fails.
    
    Attributes:
        provider: Optional provider name for context
    
    Examples:
        - Missing API key
        - Invalid API key
        - API key file not found
    """
    
    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, cause=cause)
        self.provider = provider


class FileError(MsgModelError):
    """
    Raised when file operations fail.
    
    Attributes:
        filename: Optional filename that caused the error
    
    Examples:
        - File not found
        - Unable to read file
        - Invalid file format
    """
    
    def __init__(
        self,
        message: str,
        *,
        filename: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, cause=cause)
        self.filename = filename


class APIError(MsgModelError):
    """
    Raised when an API call fails.
    
    Attributes:
        status_code: HTTP status code from the API response
        response_text: Raw response text from the API
        provider: Optional provider name for context
    """
    
    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        response_text: Optional[str] = None,
        *,
        provider: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, cause=cause)
        self.status_code = status_code
        self.response_text = response_text
        self.provider = provider


class ProviderError(APIError):
    """
    Raised when a provider-specific error occurs.
    
    Inherits from APIError for backward compatibility.
    
    Examples:
        - Unsupported file type for provider
        - Provider-specific validation failure
        - Missing provider dependency (e.g., anthropic package)
    """
    
    def __init__(
        self,
        message: str,
        *,
        provider: Optional[str] = None,
        status_code: Optional[int] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(
            message,
            status_code=status_code,
            response_text=None,
            provider=provider,
            cause=cause
        )


class RateLimitError(ProviderError):
    """
    Raised when rate limit is exceeded.
    
    Attributes:
        retry_after: Optional seconds to wait before retrying
    
    This error is retryable - callers should wait and retry.
    """
    
    def __init__(
        self,
        message: str = "Rate limit exceeded",
        *,
        provider: Optional[str] = None,
        retry_after: Optional[float] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, provider=provider, status_code=429, cause=cause)
        self.retry_after = retry_after


class ContextLengthError(ProviderError):
    """
    Raised when prompt exceeds the model's context length.
    
    Attributes:
        max_tokens: Maximum allowed tokens for the model
        prompt_tokens: Estimated tokens in the prompt
    """
    
    def __init__(
        self,
        message: str = "Prompt exceeds maximum context length",
        *,
        provider: Optional[str] = None,
        max_tokens: Optional[int] = None,
        prompt_tokens: Optional[int] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, provider=provider, status_code=400, cause=cause)
        self.max_tokens = max_tokens
        self.prompt_tokens = prompt_tokens


class ServiceUnavailableError(ProviderError):
    """
    Raised when the provider service is temporarily unavailable.
    
    This error is retryable - callers should wait and retry.
    """
    
    def __init__(
        self,
        message: str = "Service temporarily unavailable",
        *,
        provider: Optional[str] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, provider=provider, status_code=503, cause=cause)


class StreamingError(MsgModelError):
    """
    Raised when streaming-specific errors occur.
    
    Attributes:
        chunks_received: Number of chunks received before error (if known)
        sample_chunks: Optional list of sample chunks for debugging
    
    Examples:
        - Connection interrupted during streaming
        - Invalid streaming response format
        - Timeout during streaming
        - No chunks extracted from stream (format mismatch or premature termination)
    """
    
    def __init__(
        self,
        message: str,
        *,
        chunks_received: Optional[int] = None,
        sample_chunks: Optional[list] = None,
        cause: Optional[Exception] = None
    ):
        super().__init__(message, cause=cause)
        self.chunks_received = chunks_received
        self.sample_chunks = sample_chunks or []
    
    @staticmethod
    def detect_error_in_chunk(chunk: dict) -> Optional[dict]:
        """
        Detect if a streaming chunk contains an error structure.
        
        Recognizes error formats from both OpenAI and Gemini APIs:
        - OpenAI: {"error": {"message": "...", "type": "..."}}
        - Gemini: {"error": {"message": "...", "code": ..., "status": "..."}}
        
        Args:
            chunk: The parsed JSON chunk from the stream
            
        Returns:
            The error dict if found, None otherwise
        """
        if isinstance(chunk, dict) and "error" in chunk:
            error_obj = chunk.get("error")
            if isinstance(error_obj, dict):
                return error_obj
        return None
    
    @staticmethod
    def is_rate_limit_error(error_obj: dict) -> bool:
        """
        Determine if an error object represents a rate limit error.
        
        Detects:
        - OpenAI: error_type == "rate_limit_error"
        - Gemini: status == "RESOURCE_EXHAUSTED" or "quota" in message
        - Generic: "rate" or "quota" or "limit" in message (case-insensitive)
        
        Args:
            error_obj: The error dict from a chunk
            
        Returns:
            True if this is a rate limit error, False otherwise
        """
        if not isinstance(error_obj, dict):
            return False
        
        # Check OpenAI error type
        if error_obj.get("type") == "rate_limit_error":
            return True
        
        # Check Gemini status
        if error_obj.get("status") == "RESOURCE_EXHAUSTED":
            return True
        
        # Check message content
        message = (error_obj.get("message") or "").lower()
        return any(keyword in message for keyword in ["rate", "quota", "limit", "exhausted"])
