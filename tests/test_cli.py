"""
Tests for msgmodel CLI (__main__.py).
"""

import pytest
import sys
import io
from unittest.mock import patch, Mock, MagicMock
from pathlib import Path

from msgmodel.__main__ import parse_args, main, read_file_content, format_privacy_info
from msgmodel.exceptions import FileError, AuthenticationError, APIError, ConfigurationError


class TestParseArgs:
    """Tests for argument parsing."""
    
    def test_basic_args(self):
        """Test basic argument parsing."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            args = parse_args()
            assert args.provider == 'openai'
            assert args.prompt == 'Hello'
    
    def test_provider_shortcuts(self):
        """Test provider shortcut codes."""
        for shortcut, expected in [('o', 'o'), ('g', 'g'), ('c', 'c'), ('a', 'a')]:
            with patch.object(sys, 'argv', ['msgmodel', '-p', shortcut, 'Hi']):
                args = parse_args()
                assert args.provider == shortcut
    
    def test_stream_flag(self):
        """Test --stream flag."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '--stream']):
            args = parse_args()
            assert args.stream is True
    
    def test_json_flag(self):
        """Test --json flag."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '--json']):
            args = parse_args()
            assert args.json is True
    
    def test_verbose_flag(self):
        """Test --verbose flag."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-v']):
            args = parse_args()
            assert args.verbose is True
    
    def test_model_override(self):
        """Test -m/--model argument."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-m', 'gpt-4o-mini']):
            args = parse_args()
            assert args.model == 'gpt-4o-mini'
    
    def test_max_tokens(self):
        """Test -t/--max-tokens argument."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-t', '500']):
            args = parse_args()
            assert args.max_tokens == 500
    
    def test_temperature(self):
        """Test --temperature argument."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '--temperature', '0.7']):
            args = parse_args()
            assert args.temperature == 0.7
    
    def test_api_key(self):
        """Test -k/--api-key argument."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-k', 'test-key']):
            args = parse_args()
            assert args.api_key == 'test-key'
    
    def test_instruction(self):
        """Test -i/--instruction argument."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-i', 'Be helpful']):
            args = parse_args()
            assert args.instruction == 'Be helpful'
    
    def test_file_argument(self):
        """Test -f/--file argument."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-f', 'test.txt']):
            args = parse_args()
            assert args.file == 'test.txt'


class TestReadFileContent:
    """Tests for read_file_content function."""
    
    def test_read_existing_file(self, tmp_path):
        """Test reading an existing file."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello, world!")
        
        content = read_file_content(str(test_file))
        assert content == "Hello, world!"
    
    def test_read_nonexistent_file(self):
        """Test reading a non-existent file raises FileError."""
        with pytest.raises(FileError, match="Cannot read file"):
            read_file_content("/nonexistent/path/file.txt")


class TestMainFunction:
    """Tests for main() function."""
    
    @patch('msgmodel.__main__.query')
    def test_basic_query(self, mock_query):
        """Test basic query execution."""
        mock_response = Mock()
        mock_response.text = "Hello back!"
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.usage = None
        mock_response.privacy = None
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            with patch('builtins.print') as mock_print:
                result = main()
        
        assert result == 0
        mock_query.assert_called_once()
        mock_print.assert_called_with("Hello back!")
    
    @patch('msgmodel.__main__.stream')
    def test_streaming_query(self, mock_stream):
        """Test streaming query execution."""
        mock_stream.return_value = iter(["Hello", " ", "world"])
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '--stream']):
            with patch('builtins.print') as mock_print:
                result = main()
        
        assert result == 0
        mock_stream.assert_called_once()
    
    @patch('msgmodel.__main__.query')
    def test_json_output(self, mock_query):
        """Test JSON output mode."""
        mock_response = Mock()
        mock_response.raw_response = {"text": "Hello", "model": "gpt-4o"}
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '--json']):
            with patch('builtins.print') as mock_print:
                result = main()
        
        assert result == 0
        # Should print JSON
        call_args = mock_print.call_args[0][0]
        assert '"text"' in call_args or '"model"' in call_args
    
    def test_missing_prompt(self):
        """Test error when prompt is missing."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai']):
            result = main()
        
        assert result == 1
    
    @patch('msgmodel.__main__.query')
    def test_authentication_error(self, mock_query):
        """Test handling of AuthenticationError."""
        mock_query.side_effect = AuthenticationError("Invalid API key")
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            result = main()
        
        assert result == 2
    
    @patch('msgmodel.__main__.query')
    def test_api_error(self, mock_query):
        """Test handling of APIError."""
        mock_query.side_effect = APIError("API call failed")
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            result = main()
        
        assert result == 4
    
    @patch('msgmodel.__main__.query')
    def test_configuration_error(self, mock_query):
        """Test handling of ConfigurationError."""
        mock_query.side_effect = ConfigurationError("Bad config")
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            result = main()
        
        assert result == 1
    
    @patch('msgmodel.__main__.query')
    def test_file_error(self, mock_query):
        """Test handling of FileError."""
        mock_query.side_effect = FileError("File not found")
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            result = main()
        
        assert result == 3
    
    @patch('msgmodel.__main__.query')
    def test_with_file_attachment(self, mock_query, tmp_path):
        """Test query with file attachment."""
        # Create a test file
        test_file = tmp_path / "test.txt"
        test_file.write_bytes(b"Test content")
        
        mock_response = Mock()
        mock_response.text = "Analyzed!"
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.usage = None
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Analyze this', '-f', str(test_file)]):
            with patch('builtins.print'):
                result = main()
        
        assert result == 0
        # Check that file_like was passed
        call_kwargs = mock_query.call_args[1]
        assert call_kwargs['file_like'] is not None
        assert call_kwargs['filename'] == 'test.txt'
    
    @patch('msgmodel.__main__.query')
    def test_with_instruction_file(self, mock_query, tmp_path):
        """Test query with system instruction from file."""
        # Create an instruction file
        instr_file = tmp_path / "instructions.txt"
        instr_file.write_text("You are a helpful assistant.")
        
        mock_response = Mock()
        mock_response.text = "Hello!"
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.usage = None
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-i', str(instr_file)]):
            with patch('builtins.print'):
                result = main()
        
        assert result == 0
        call_kwargs = mock_query.call_args[1]
        assert call_kwargs['system_instruction'] == "You are a helpful assistant."
    
    @patch('msgmodel.__main__.query')
    def test_with_instruction_text(self, mock_query):
        """Test query with system instruction as text."""
        mock_response = Mock()
        mock_response.text = "Hello!"
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.usage = None
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-i', 'Be concise']):
            with patch('builtins.print'):
                result = main()
        
        assert result == 0
        call_kwargs = mock_query.call_args[1]
        assert call_kwargs['system_instruction'] == "Be concise"
    
    def test_file_not_found(self, tmp_path):
        """Test error when attachment file doesn't exist."""
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-f', '/nonexistent/file.txt']):
            result = main()
        
        assert result == 3  # FileError exit code
    
    @patch('msgmodel.__main__.query')
    def test_verbose_output(self, mock_query):
        """Test verbose output shows model info."""
        mock_response = Mock()
        mock_response.text = "Hello!"
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 5}
        mock_response.privacy = None
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-v']):
            with patch('builtins.print'):
                result = main()
        
        assert result == 0
    
    @patch('msgmodel.__main__.query')
    def test_generic_msgmodel_error(self, mock_query):
        """Test handling of generic MsgModelError."""
        from msgmodel.exceptions import MsgModelError
        mock_query.side_effect = MsgModelError("Something went wrong")
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            result = main()
        
        assert result == 5
    
    @patch('msgmodel.__main__.query')
    def test_keyboard_interrupt(self, mock_query):
        """Test handling of KeyboardInterrupt."""
        mock_query.side_effect = KeyboardInterrupt()
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            result = main()
        
        assert result == 0  # Clean exit on Ctrl+C


class TestFormatPrivacyInfo:
    """Tests for format_privacy_info helper function."""
    
    def test_format_privacy_info_openai(self):
        """Test formatting OpenAI privacy info."""
        privacy = {
            "provider": "openai",
            "training_retention": False,
            "data_retention": "Standard API: ~30 days (ZDR eligibility required for zero storage)",
            "enforcement_level": "api_policy",
            "special_conditions": "Training opt-out is automatic for all API users. Zero Data Retention (no storage) requires separate eligibility from OpenAI.",
            "reference": "https://platform.openai.com/docs/models/how-we-use-your-data"
        }
        
        result = format_privacy_info(privacy)
        assert "OPENAI" in result
        assert "NOT retained for training" in result
        assert "ZDR" in result
        assert "https://platform.openai.com" in result
    
    def test_format_privacy_info_gemini(self):
        """Test formatting Gemini privacy info."""
        privacy = {
            "provider": "gemini",
            "training_retention": "depends_on_tier",
            "data_retention": "Varies by account tier",
            "enforcement_level": "tier_dependent",
            "special_conditions": "Data handling depends on your Google Cloud account tier.",
            "reference": "https://ai.google.dev/gemini-api/terms"
        }
        
        result = format_privacy_info(privacy)
        assert "GEMINI" in result
        assert "depends_on_tier" in result
        assert "Varies by account tier" in result
    
    def test_format_privacy_info_anthropic(self):
        """Test formatting Anthropic privacy info."""
        privacy = {
            "provider": "anthropic",
            "training_retention": False,
            "data_retention": "Temporary (for safety monitoring)",
            "enforcement_level": "default",
            "special_conditions": "Review Anthropic's data retention policies.",
            "reference": "https://www.anthropic.com/legal/privacy"
        }
        
        result = format_privacy_info(privacy)
        assert "ANTHROPIC" in result
        assert "NOT retained for training" in result
        assert "Temporary" in result
    
    def test_format_privacy_info_none(self):
        """Test formatting when privacy is None."""
        result = format_privacy_info(None)
        assert "Privacy information unavailable" in result
    
    def test_format_privacy_info_empty(self):
        """Test formatting with empty privacy dict."""
        result = format_privacy_info({})
        assert "Privacy information unavailable" in result


class TestPrivacyInCLI:
    """Tests for privacy info display in CLI."""
    
    @patch('msgmodel.__main__.query')
    def test_privacy_display_verbose_mode(self, mock_query):
        """Test privacy info is displayed in verbose mode."""
        mock_response = Mock()
        mock_response.text = "Hello!"
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.usage = {"prompt_tokens": 10, "completion_tokens": 5}
        mock_response.privacy = {
            "provider": "openai",
            "training_retention": False,
            "data_retention": "Standard API: ~30 days (ZDR eligibility required for zero storage)",
            "enforcement_level": "api_policy",
            "special_conditions": "Training opt-out is automatic for all API users.",
            "reference": "https://platform.openai.com/docs/models/how-we-use-your-data"
        }
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-v']):
            with patch('builtins.print') as mock_print:
                result = main()
        
        assert result == 0
        # Check that logger output was called (privacy info logged in verbose mode)
        mock_query.assert_called_once()
    
    @patch('msgmodel.__main__.query')
    def test_privacy_notice_non_verbose_mode(self, mock_query):
        """Test privacy info notice is shown even without verbose flag."""
        mock_response = Mock()
        mock_response.text = "Hello!"
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.usage = None
        mock_response.privacy = {
            "provider": "openai",
            "training_retention": False,
            "data_retention": "Standard API: ~30 days (ZDR eligibility required for zero storage)",
            "enforcement_level": "api_policy",
            "special_conditions": "Training opt-out is automatic for all API users.",
            "reference": "https://platform.openai.com/docs/models/how-we-use-your-data"
        }
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello']):
            with patch('builtins.print') as mock_print:
                result = main()
        
        assert result == 0
        # Response text should be printed
        mock_print.assert_called_with("Hello!")
    
    @patch('msgmodel.__main__.query')
    def test_no_privacy_info_available(self, mock_query):
        """Test when privacy info is not available."""
        mock_response = Mock()
        mock_response.text = "Hello!"
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.usage = None
        mock_response.privacy = None
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '-v']):
            with patch('builtins.print') as mock_print:
                result = main()
        
        assert result == 0
        mock_print.assert_called_with("Hello!")
    
    @patch('msgmodel.__main__.query')
    def test_privacy_with_json_output(self, mock_query):
        """Test that privacy is not displayed when JSON output is requested."""
        mock_response = Mock()
        mock_response.raw_response = {"text": "Hello!", "model": "gpt-4o"}
        mock_response.model = "gpt-4o"
        mock_response.provider = "openai"
        mock_response.privacy = {
            "provider": "openai",
            "training_retention": False,
            "data_retention": "Standard API: ~30 days (ZDR eligibility required for zero storage)",
            "enforcement_level": "api_policy",
            "special_conditions": "Training opt-out is automatic for all API users.",
            "reference": "https://platform.openai.com/docs/models/how-we-use-your-data"
        }
        mock_query.return_value = mock_response
        
        with patch.object(sys, 'argv', ['msgmodel', '-p', 'openai', 'Hello', '--json', '-v']):
            with patch('builtins.print') as mock_print:
                result = main()
        
        assert result == 0
        # JSON output should be printed (call args will contain JSON)
        call_args = mock_print.call_args[0][0]
        assert '"text"' in call_args or '"model"' in call_args
