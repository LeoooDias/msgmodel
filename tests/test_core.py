"""
Tests for msgmodel.core module.

Note: These tests focus on validation and utility functions.
API calls are mocked to avoid requiring actual API keys.
"""

import os
import io
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from msgmodel.core import (
    _get_api_key,
    _prepare_file_data,
    _prepare_file_like_data,
    _validate_max_tokens,
    query,
    stream,
    LLMResponse,
)
from msgmodel.config import Provider, OpenAIConfig
from msgmodel.exceptions import (
    ConfigurationError,
    AuthenticationError,
    FileError,
)


class TestValidateMaxTokens:
    """Tests for _validate_max_tokens function."""
    
    def test_valid_values(self):
        """Test that valid values don't raise."""
        _validate_max_tokens(1)
        _validate_max_tokens(100)
        _validate_max_tokens(1000)
        _validate_max_tokens(100000)
    
    def test_zero_raises(self):
        """Test that zero raises ConfigurationError."""
        with pytest.raises(ConfigurationError, match="at least 1"):
            _validate_max_tokens(0)
    
    def test_negative_raises(self):
        """Test that negative values raise ConfigurationError."""
        with pytest.raises(ConfigurationError, match="at least 1"):
            _validate_max_tokens(-1)
    
    def test_very_large_warns(self, caplog):
        """Test that very large values log a warning."""
        import logging
        with caplog.at_level(logging.WARNING):
            _validate_max_tokens(1000001)
        assert "very large" in caplog.text


class TestGetApiKey:
    """Tests for _get_api_key function."""
    
    def test_direct_key_takes_priority(self):
        """Test that directly provided key is used first."""
        key = _get_api_key(Provider.OPENAI, api_key="sk-direct-key")
        assert key == "sk-direct-key"
    
    def test_env_var_fallback(self):
        """Test fallback to environment variable."""
        with patch.dict(os.environ, {"OPENAI_API_KEY": "sk-env-key"}):
            key = _get_api_key(Provider.OPENAI)
            assert key == "sk-env-key"
    
    def test_file_fallback(self):
        """Test fallback to key file."""
        with tempfile.TemporaryDirectory() as tmpdir:
            key_file = Path(tmpdir) / "openai-api.key"
            key_file.write_text("sk-file-key")
            
            # Change to temp directory and patch the file path
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                # Clear env var
                with patch.dict(os.environ, {}, clear=True):
                    key = _get_api_key(Provider.OPENAI)
                    assert key == "sk-file-key"
            finally:
                os.chdir(original_cwd)
    
    def test_no_key_raises(self):
        """Test that missing key raises AuthenticationError."""
        with tempfile.TemporaryDirectory() as tmpdir:
            original_cwd = os.getcwd()
            os.chdir(tmpdir)
            try:
                with patch.dict(os.environ, {}, clear=True):
                    with pytest.raises(AuthenticationError, match="No API key found"):
                        _get_api_key(Provider.OPENAI)
            finally:
                os.chdir(original_cwd)


class TestPrepareFileData:
    """Tests for _prepare_file_data function."""
    
    def test_nonexistent_file_raises(self):
        """Test that nonexistent file raises FileError."""
        with pytest.raises(FileError, match="File not found"):
            _prepare_file_data("/nonexistent/path/to/file.jpg")
    
    def test_image_file(self):
        """Test preparing image file data."""
        with tempfile.NamedTemporaryFile(suffix=".jpg", delete=False) as f:
            f.write(b"fake image data")
            f.flush()
            
            try:
                data = _prepare_file_data(f.name)
                assert data["mime_type"] == "image/jpeg"
                assert "data" in data
                assert data["filename"].endswith(".jpg")
            finally:
                os.unlink(f.name)
    
    def test_pdf_file(self):
        """Test preparing PDF file data."""
        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=False) as f:
            f.write(b"fake pdf data")
            f.flush()
            
            try:
                data = _prepare_file_data(f.name)
                assert data["mime_type"] == "application/pdf"
            finally:
                os.unlink(f.name)
    
    def test_unknown_extension(self):
        """Test that unknown extension uses octet-stream."""
        with tempfile.NamedTemporaryFile(suffix=".xyz123", delete=False) as f:
            f.write(b"unknown data")
            f.flush()
            
            try:
                data = _prepare_file_data(f.name)
                assert data["mime_type"] == "application/octet-stream"
            finally:
                os.unlink(f.name)


class TestPrepareFileLikeData:
    """Tests for _prepare_file_like_data function."""
    
    def test_bytesio_with_image(self):
        """Test preparing BytesIO with image data."""
        file_obj = io.BytesIO(b"fake image data")
        data = _prepare_file_like_data(file_obj, filename="photo.jpg")
        
        assert data["mime_type"] == "image/jpeg"
        assert "data" in data
        assert data["filename"] == "photo.jpg"
        assert data["is_file_like"] is True
    
    def test_bytesio_with_pdf(self):
        """Test preparing BytesIO with PDF data."""
        file_obj = io.BytesIO(b"fake pdf data")
        data = _prepare_file_like_data(file_obj, filename="document.pdf")
        
        assert data["mime_type"] == "application/pdf"
        assert data["filename"] == "document.pdf"
    
    def test_bytesio_with_unknown_extension(self):
        """Test that unknown extension uses octet-stream."""
        file_obj = io.BytesIO(b"unknown data")
        data = _prepare_file_like_data(file_obj, filename="file.unknownextension")
        
        assert data["mime_type"] == "application/octet-stream"
    
    def test_bytesio_default_filename(self):
        """Test default filename when not provided."""
        file_obj = io.BytesIO(b"data")
        data = _prepare_file_like_data(file_obj)
        
        assert data["filename"] == "upload.bin"
    
    def test_bytesio_position_reset(self):
        """Test that position is reset after reading."""
        file_obj = io.BytesIO(b"test data")
        file_obj.seek(5)  # Move to position 5
        
        _prepare_file_like_data(file_obj, filename="test.txt")
        
        # Should be back at beginning
        assert file_obj.tell() == 0
    
    def test_bytesio_reuse(self):
        """Test that BytesIO can be reused multiple times."""
        file_obj = io.BytesIO(b"reusable data")
        
        data1 = _prepare_file_like_data(file_obj, filename="file1.bin")
        data2 = _prepare_file_like_data(file_obj, filename="file2.bin")
        
        # Both should have the same encoded data
        assert data1["data"] == data2["data"]
        assert file_obj.tell() == 0  # Should be at start
    
    def test_invalid_file_like_raises(self):
        """Test that invalid file-like objects raise FileError."""
        class FakeFileObject:
            def read(self):
                raise IOError("Read error")
        
        with pytest.raises(FileError, match="Failed to read from file-like object"):
            _prepare_file_like_data(FakeFileObject())
    
    def test_non_seekable_file_raises(self):
        """Test that non-seekable file-like objects raise FileError."""
        class NonSeekableFile:
            def read(self):
                return b"data"
            
            def seek(self, pos):
                raise OSError("Not seekable")
        
        with pytest.raises(FileError, match="Failed to read from file-like object"):
            _prepare_file_like_data(NonSeekableFile())



class TestLLMResponse:
    """Tests for LLMResponse dataclass."""
    
    def test_basic_response(self):
        """Test creating a basic response."""
        response = LLMResponse(
            text="Hello, world!",
            raw_response={"output": "Hello, world!"},
            model="gpt-4o",
            provider="openai",
        )
        assert response.text == "Hello, world!"
        assert response.model == "gpt-4o"
        assert response.provider == "openai"
        assert response.usage is None
    
    def test_response_with_usage(self):
        """Test creating a response with usage info."""
        response = LLMResponse(
            text="Hello!",
            raw_response={},
            model="claude-3-opus",
            provider="claude",
            usage={"input_tokens": 10, "output_tokens": 5},
        )
        assert response.usage == {"input_tokens": 10, "output_tokens": 5}


class TestQueryFunction:
    """Tests for the query function."""
    
    def test_provider_string_conversion(self):
        """Test that provider strings are converted correctly."""
        with patch("msgmodel.core._get_api_key") as mock_key:
            mock_key.return_value = "sk-test"
            
            with patch("msgmodel.core.OpenAIProvider") as mock_provider:
                mock_instance = MagicMock()
                mock_instance.query.return_value = {"output": []}
                mock_instance.extract_text.return_value = "Hello"
                mock_provider.return_value = mock_instance
                
                # Test shorthand
                query("o", "Hello")
                mock_provider.assert_called()
    
    def test_config_override(self):
        """Test that config parameters can be overridden."""
        config = OpenAIConfig(max_tokens=500)
        
        with patch("msgmodel.core._get_api_key") as mock_key:
            mock_key.return_value = "sk-test"
            
            with patch("msgmodel.core.OpenAIProvider") as mock_provider:
                mock_instance = MagicMock()
                mock_instance.query.return_value = {"output": []}
                mock_instance.extract_text.return_value = "Hello"
                mock_provider.return_value = mock_instance
                
                # Override max_tokens
                query("openai", "Hello", config=config, max_tokens=1000)
                
                # Config should have been modified
                assert config.max_tokens == 1000    
    def test_file_path_and_file_like_mutually_exclusive(self):
        """Test that providing both file_path and file_like raises ConfigurationError."""
        with patch("msgmodel.core._get_api_key") as mock_key:
            mock_key.return_value = "sk-test"
            
            file_obj = io.BytesIO(b"test data")
            
            with pytest.raises(ConfigurationError, match="Cannot specify both file_path and file_like"):
                query("openai", "Hello", file_path="/fake/path.txt", file_like=file_obj)
    
    def test_file_like_parameter(self):
        """Test that file_like parameter is properly handled."""
        with patch("msgmodel.core._get_api_key") as mock_key:
            mock_key.return_value = "sk-test"
            
            with patch("msgmodel.core.OpenAIProvider") as mock_provider:
                mock_instance = MagicMock()
                mock_instance.query.return_value = {"output": []}
                mock_instance.extract_text.return_value = "Hello"
                mock_provider.return_value = mock_instance
                
                file_obj = io.BytesIO(b"test data")
                query("openai", "Analyze this", file_like=file_obj)
                
                # Verify the provider.query was called with file_data
                call_args = mock_instance.query.call_args
                assert call_args is not None
                # file_data should be the third argument
                file_data = call_args[0][2]
                assert file_data is not None
                assert file_data["is_file_like"] is True


class TestStreamFunction:
    """Tests for the stream function."""
    
    def test_file_path_and_file_like_mutually_exclusive(self):
        """Test that providing both file_path and file_like raises ConfigurationError."""
        with patch("msgmodel.core._get_api_key") as mock_key:
            mock_key.return_value = "sk-test"
            
            file_obj = io.BytesIO(b"test data")
            
            with pytest.raises(ConfigurationError, match="Cannot specify both file_path and file_like"):
                list(stream("openai", "Hello", file_path="/fake/path.txt", file_like=file_obj))
    
    def test_file_like_parameter(self):
        """Test that file_like parameter is properly handled in stream."""
        with patch("msgmodel.core._get_api_key") as mock_key:
            mock_key.return_value = "sk-test"
            
            with patch("msgmodel.core.OpenAIProvider") as mock_provider:
                mock_instance = MagicMock()
                mock_instance.stream.return_value = iter(["Hello ", "world"])
                mock_provider.return_value = mock_instance
                
                file_obj = io.BytesIO(b"test data")
                result = list(stream("openai", "Analyze this", file_like=file_obj))
                
                assert result == ["Hello ", "world"]
                
                # Verify the provider.stream was called with file_data
                call_args = mock_instance.stream.call_args
                assert call_args is not None
                # file_data should be the third argument
                file_data = call_args[0][2]
                assert file_data is not None
                assert file_data["is_file_like"] is True