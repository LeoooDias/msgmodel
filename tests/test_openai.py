"""
Tests for msgmodel.providers.openai module.
"""

import pytest
import json
import base64
from unittest.mock import Mock, patch, MagicMock

from msgmodel.providers.openai import OpenAIProvider
from msgmodel.config import OpenAIConfig
from msgmodel.exceptions import APIError, StreamingError


class TestOpenAIProviderInit:
    """Tests for OpenAIProvider initialization."""
    
    def test_init_with_api_key(self):
        """Test initialization with API key."""
        provider = OpenAIProvider("test-api-key")
        assert provider.api_key == "test-api-key"
        assert isinstance(provider.config, OpenAIConfig)
    
    def test_init_with_custom_config(self):
        """Test initialization with custom config."""
        config = OpenAIConfig(model="gpt-4o-mini", max_tokens=2000)
        provider = OpenAIProvider("test-api-key", config)
        assert provider.config.model == "gpt-4o-mini"
        assert provider.config.max_tokens == 2000


class TestOpenAIProviderHeaders:
    """Tests for header building."""
    
    def test_build_headers(self):
        """Test that headers are built correctly."""
        provider = OpenAIProvider("test-api-key")
        headers = provider._build_headers()
        
        assert headers["Content-Type"] == "application/json"
        assert headers["Authorization"] == "Bearer test-api-key"
        assert headers["X-OpenAI-No-Store"] == "true"


class TestOpenAIProviderContent:
    """Tests for content building."""
    
    def test_build_content_text_only(self):
        """Test content building with text only."""
        provider = OpenAIProvider("test-api-key")
        content = provider._build_content("Hello, world!")
        
        assert len(content) == 1
        assert content[0]["type"] == "text"
        assert content[0]["text"] == "Hello, world!"
    
    def test_build_content_with_image(self):
        """Test content building with image file."""
        provider = OpenAIProvider("test-api-key")
        file_data = {
            "mime_type": "image/png",
            "data": base64.b64encode(b"fake image data").decode(),
            "filename": "test.png"
        }
        content = provider._build_content("Describe this", file_data)
        
        assert len(content) == 2
        assert content[0]["type"] == "image_url"
        assert "data:image/png;base64," in content[0]["image_url"]["url"]
        assert content[1]["type"] == "text"
        assert content[1]["text"] == "Describe this"
    
    def test_build_content_with_text_file(self):
        """Test content building with text file."""
        provider = OpenAIProvider("test-api-key")
        file_data = {
            "mime_type": "text/plain",
            "data": base64.b64encode(b"Hello from file").decode(),
            "filename": "readme.txt"
        }
        content = provider._build_content("Analyze this", file_data)
        
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert "Hello from file" in content[0]["text"]
        assert "readme.txt" in content[0]["text"]
    
    def test_build_content_with_binary_file(self):
        """Test content building with unsupported binary file."""
        provider = OpenAIProvider("test-api-key")
        file_data = {
            "mime_type": "application/octet-stream",
            "data": base64.b64encode(b"\x00\x01\x02").decode(),
            "filename": "data.bin"
        }
        content = provider._build_content("Process this", file_data)
        
        assert len(content) == 2
        assert content[0]["type"] == "text"
        assert "data.bin" in content[0]["text"]
        assert "application/octet-stream" in content[0]["text"]
    
    def test_build_content_with_empty_text_file(self):
        """Test content building with empty text file."""
        provider = OpenAIProvider("test-api-key")
        file_data = {
            "mime_type": "text/plain",
            "data": base64.b64encode(b"   ").decode(),  # Just whitespace
            "filename": "empty.txt"
        }
        content = provider._build_content("Analyze this", file_data)
        
        # Empty/whitespace text file should not add a text content block
        assert len(content) == 1
        assert content[0]["text"] == "Analyze this"
    
    def test_build_content_text_decode_error(self):
        """Test content building when text decode fails."""
        provider = OpenAIProvider("test-api-key")
        file_data = {
            "mime_type": "text/plain",
            "data": "not-valid-base64!!!",  # Invalid base64
            "filename": "bad.txt"
        }
        content = provider._build_content("Analyze this", file_data)
        
        # Should handle gracefully (empty text won't be added)
        assert len(content) == 1


class TestOpenAIMaxTokensSupport:
    """Tests for max_completion_tokens vs max_tokens selection."""
    
    def test_gpt4o_uses_max_completion_tokens(self):
        """Test that GPT-4o uses max_completion_tokens."""
        provider = OpenAIProvider("test-api-key")
        assert provider._supports_max_completion_tokens("gpt-4o") is True
        assert provider._supports_max_completion_tokens("gpt-4o-mini") is True
        assert provider._supports_max_completion_tokens("gpt-4o-2024-08-06") is True
    
    def test_gpt4_turbo_uses_max_completion_tokens(self):
        """Test that GPT-4-turbo uses max_completion_tokens."""
        provider = OpenAIProvider("test-api-key")
        assert provider._supports_max_completion_tokens("gpt-4-turbo") is True
        assert provider._supports_max_completion_tokens("gpt-4-turbo-preview") is True
    
    def test_legacy_gpt4_uses_max_tokens(self):
        """Test that legacy GPT-4 uses max_tokens."""
        provider = OpenAIProvider("test-api-key")
        assert provider._supports_max_completion_tokens("gpt-4") is False
        assert provider._supports_max_completion_tokens("gpt-4-0613") is False
        assert provider._supports_max_completion_tokens("gpt-4-0125-preview") is False
    
    def test_gpt4_turbo_variant_not_caught_by_legacy_check(self):
        """Test that gpt-4-0*-turbo variants are NOT caught by legacy gpt-4-0 prefix.
        
        This tests the specific continue statement that ensures models like
        gpt-4-0125-turbo (hypothetical) or any gpt-4-0*-turbo variant uses
        max_completion_tokens, not max_tokens.
        """
        provider = OpenAIProvider("test-api-key")
        # A hypothetical model starting with gpt-4-0 but containing turbo
        # should still use max_completion_tokens (modern) due to the continue branch
        assert provider._supports_max_completion_tokens("gpt-4-0125-turbo") is True
    
    def test_legacy_gpt35_uses_max_tokens(self):
        """Test that GPT-3.5-turbo uses max_tokens."""
        provider = OpenAIProvider("test-api-key")
        assert provider._supports_max_completion_tokens("gpt-3.5-turbo") is False
        assert provider._supports_max_completion_tokens("gpt-3.5-turbo-0613") is False
    
    def test_future_models_use_max_completion_tokens(self):
        """Test that future/unknown models default to max_completion_tokens."""
        provider = OpenAIProvider("test-api-key")
        assert provider._supports_max_completion_tokens("gpt-5") is True
        assert provider._supports_max_completion_tokens("gpt-6-ultra") is True
        assert provider._supports_max_completion_tokens("o1-preview") is True


class TestOpenAIProviderPayload:
    """Tests for payload building."""
    
    def test_build_payload_basic(self):
        """Test basic payload building."""
        provider = OpenAIProvider("test-api-key")
        payload = provider._build_payload("Hello")
        
        assert payload["model"] == "gpt-4o"
        assert "max_completion_tokens" in payload  # GPT-4o uses new param
        assert len(payload["messages"]) == 1
        assert payload["messages"][0]["role"] == "user"
    
    def test_build_payload_with_system(self):
        """Test payload building with system instruction."""
        provider = OpenAIProvider("test-api-key")
        payload = provider._build_payload("Hello", system_instruction="Be helpful")
        
        assert len(payload["messages"]) == 2
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "Be helpful"
        assert payload["messages"][1]["role"] == "user"
    
    def test_build_payload_with_stream(self):
        """Test payload building for streaming."""
        provider = OpenAIProvider("test-api-key")
        payload = provider._build_payload("Hello", stream=True)
        
        assert payload["stream"] is True
    
    def test_build_payload_legacy_model_uses_max_tokens(self):
        """Test that legacy models use max_tokens in payload."""
        config = OpenAIConfig(model="gpt-3.5-turbo")
        provider = OpenAIProvider("test-api-key", config)
        payload = provider._build_payload("Hello")
        
        assert "max_tokens" in payload
        assert "max_completion_tokens" not in payload
    
    def test_build_payload_includes_temperature(self):
        """Test that payload includes temperature."""
        provider = OpenAIProvider("test-api-key")
        payload = provider._build_payload("Hello")
        
        assert "temperature" in payload
        assert "top_p" in payload


class TestOpenAIProviderQuery:
    """Tests for query method."""
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_query_success(self, mock_post):
        """Test successful query."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {
            "choices": [{"message": {"content": "Hello back!"}}],
            "model": "gpt-4o"
        }
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        result = provider.query("Hello")
        
        assert result["choices"][0]["message"]["content"] == "Hello back!"
        mock_post.assert_called_once()
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_query_with_system_instruction(self, mock_post):
        """Test query with system instruction."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.json.return_value = {"choices": [{"message": {"content": "OK"}}]}
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        provider.query("Hello", system_instruction="Be concise")
        
        call_args = mock_post.call_args
        payload = json.loads(call_args[1]["data"])
        assert payload["messages"][0]["role"] == "system"
        assert payload["messages"][0]["content"] == "Be concise"
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_query_api_error(self, mock_post):
        """Test query handling API error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 401
        mock_response.text = "Unauthorized"
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(APIError) as exc_info:
            provider.query("Hello")
        
        assert exc_info.value.status_code == 401
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_query_request_exception(self, mock_post):
        """Test query handling request exception."""
        import requests
        mock_post.side_effect = requests.RequestException("Connection failed")
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(APIError) as exc_info:
            provider.query("Hello")
        
        assert "Connection failed" in str(exc_info.value)


class TestOpenAIProviderStream:
    """Tests for stream method."""
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_success(self, mock_post):
        """Test successful streaming."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" world"}}]}',
            b'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        chunks = list(provider.stream("Hi"))
        
        assert chunks == ["Hello", " world"]
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_with_callback(self, mock_post):
        """Test streaming with callback."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" world"}}]}',
            b'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        collected = []
        def callback(chunk):
            collected.append(chunk)
            return True
        
        provider = OpenAIProvider("test-api-key")
        chunks = list(provider.stream("Hi", on_chunk=callback))
        
        assert collected == ["Hello", " world"]
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_abort_via_callback(self, mock_post):
        """Test aborting stream via callback."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: {"choices":[{"delta":{"content":" world"}}]}',
            b'data: {"choices":[{"delta":{"content":"!"}}]}',
            b'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        call_count = [0]
        def callback(chunk):
            call_count[0] += 1
            # Return True for first two chunks, False on third
            return call_count[0] < 3
        
        provider = OpenAIProvider("test-api-key")
        chunks = list(provider.stream("Hi", on_chunk=callback))
        
        # Callback returns False on third chunk, so it's not yielded
        assert chunks == ["Hello", " world"]
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_api_error(self, mock_post):
        """Test streaming API error."""
        mock_response = Mock()
        mock_response.ok = False
        mock_response.status_code = 500
        mock_response.text = "Server error"
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(APIError) as exc_info:
            list(provider.stream("Hi"))
        
        assert exc_info.value.status_code == 500
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_timeout(self, mock_post):
        """Test streaming timeout."""
        import requests
        mock_post.side_effect = requests.Timeout("Timed out")
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(StreamingError) as exc_info:
            list(provider.stream("Hi", timeout=10))
        
        assert "timed out" in str(exc_info.value).lower()
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_request_exception(self, mock_post):
        """Test streaming request exception."""
        import requests
        mock_post.side_effect = requests.RequestException("Connection failed")
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(APIError) as exc_info:
            list(provider.stream("Hi"))
        
        assert "Connection failed" in str(exc_info.value)
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_no_chunks_error(self, mock_post):
        """Test error when no chunks received."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"choices":[{"delta":{}}]}',  # No content
            b'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(StreamingError) as exc_info:
            list(provider.stream("Hi"))
        
        assert "No text chunks" in str(exc_info.value)
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_rate_limit_error(self, mock_post):
        """Test handling rate limit error in stream."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"error":{"message":"Rate limit exceeded","type":"rate_limit_error"}}'
        ]
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(APIError) as exc_info:
            list(provider.stream("Hi"))
        
        assert exc_info.value.status_code == 429
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_generic_error(self, mock_post):
        """Test handling generic error in stream."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: {"error":{"message":"Something went wrong","type":"server_error"}}'
        ]
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(APIError) as exc_info:
            list(provider.stream("Hi"))
        
        assert "server_error" in str(exc_info.value)
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_json_decode_error_skipped(self, mock_post):
        """Test that invalid JSON lines are skipped."""
        mock_response = Mock()
        mock_response.ok = True
        mock_response.iter_lines.return_value = [
            b'data: not-valid-json',
            b'data: {"choices":[{"delta":{"content":"Hello"}}]}',
            b'data: [DONE]'
        ]
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        chunks = list(provider.stream("Hi"))
        
        assert chunks == ["Hello"]
    
    @patch('msgmodel.providers.openai.requests.post')
    def test_stream_interrupted_exception(self, mock_post):
        """Test handling of unexpected exception during streaming."""
        mock_response = Mock()
        mock_response.ok = True
        
        def iter_lines_with_error():
            yield b'data: {"choices":[{"delta":{"content":"Hello"}}]}'
            raise RuntimeError("Connection lost")
        
        mock_response.iter_lines = iter_lines_with_error
        mock_post.return_value = mock_response
        
        provider = OpenAIProvider("test-api-key")
        with pytest.raises(StreamingError) as exc_info:
            list(provider.stream("Hi"))
        
        assert "interrupted" in str(exc_info.value).lower()


class TestOpenAIExtractText:
    """Tests for extract_text static method."""
    
    def test_extract_text_normal(self):
        """Test extracting text from normal response."""
        response = {
            "choices": [{"message": {"content": "Hello!"}}]
        }
        assert OpenAIProvider.extract_text(response) == "Hello!"
    
    def test_extract_text_empty_choices(self):
        """Test extracting text from response with no choices."""
        response = {"choices": []}
        assert OpenAIProvider.extract_text(response) == ""
    
    def test_extract_text_no_content(self):
        """Test extracting text when content is missing."""
        response = {"choices": [{"message": {}}]}
        assert OpenAIProvider.extract_text(response) == ""
    
    def test_extract_text_no_message(self):
        """Test extracting text when message is missing."""
        response = {"choices": [{}]}
        assert OpenAIProvider.extract_text(response) == ""
    
    def test_extract_text_invalid_structure(self):
        """Test extracting text from invalid structure."""
        response = {"something": "else"}
        assert OpenAIProvider.extract_text(response) == ""


class TestOpenAIPrivacyInfo:
    """Tests for get_privacy_info static method."""
    
    def test_get_privacy_info(self):
        """Test privacy info structure."""
        info = OpenAIProvider.get_privacy_info()
        
        assert info["provider"] == "openai"
        assert info["training_retention"] is False
        assert "not use API data for model training" in info["provider_policy"]
        assert "reference" in info
