"""
Tests for msgmodel.exceptions module.
"""

import pytest
from msgmodel.exceptions import (
    MsgModelError,
    ConfigurationError,
    AuthenticationError,
    FileError,
    APIError,
    ProviderError,
    StreamingError,
)


class TestExceptionHierarchy:
    """Tests for exception inheritance hierarchy."""
    
    def test_all_exceptions_inherit_from_base(self):
        """Test that all exceptions inherit from MsgModelError."""
        assert issubclass(ConfigurationError, MsgModelError)
        assert issubclass(AuthenticationError, MsgModelError)
        assert issubclass(FileError, MsgModelError)
        assert issubclass(APIError, MsgModelError)
        assert issubclass(ProviderError, MsgModelError)
        assert issubclass(StreamingError, MsgModelError)
    
    def test_base_inherits_from_exception(self):
        """Test that MsgModelError inherits from Exception."""
        assert issubclass(MsgModelError, Exception)


class TestAPIError:
    """Tests for APIError with additional attributes."""
    
    def test_basic_message(self):
        """Test APIError with just a message."""
        error = APIError("Something went wrong")
        assert str(error) == "Something went wrong"
        assert error.status_code is None
        assert error.response_text is None
    
    def test_with_status_code(self):
        """Test APIError with status code."""
        error = APIError("API failed", status_code=500)
        assert str(error) == "API failed"
        assert error.status_code == 500
        assert error.response_text is None
    
    def test_with_all_attributes(self):
        """Test APIError with all attributes."""
        error = APIError(
            "Rate limited",
            status_code=429,
            response_text='{"error": "too many requests"}'
        )
        assert str(error) == "Rate limited"
        assert error.status_code == 429
        assert error.response_text == '{"error": "too many requests"}'


class TestExceptionCatching:
    """Tests for exception catching patterns."""
    
    def test_catch_specific_exception(self):
        """Test catching a specific exception type."""
        with pytest.raises(AuthenticationError):
            raise AuthenticationError("Invalid API key")
    
    def test_catch_base_exception(self):
        """Test catching base exception catches all derived."""
        with pytest.raises(MsgModelError):
            raise ConfigurationError("Bad config")
        
        with pytest.raises(MsgModelError):
            raise APIError("API failed")
        
        with pytest.raises(MsgModelError):
            raise StreamingError("Stream interrupted")
