"""
Tests for msgmodel.core module.

Note: These tests focus on validation and utility functions.
API calls are mocked to avoid requiring actual API keys.
"""

import os
import pytest
from unittest.mock import patch, MagicMock
from pathlib import Path
import tempfile

from msgmodel.core import (
    _get_api_key,
    _prepare_file_data,
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
