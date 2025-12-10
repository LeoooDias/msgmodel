# msgModel

A Python script for interacting with multiple Large Language Model (LLM) providers through a single interface and common syntax.

## Overview

`msgModel.py` provides a consistent command-line interface to interact with three major LLM providers:
- **OpenAI** (GPT models)
- **Google Gemini**
- **Anthropic Claude**

This tool allows you to send prompts with optional file attachments (images, PDFs, text files) and receive responses from any of these providers using a simple, unified syntax.

## Features

- **Multi-provider support**: Switch between OpenAI, Gemini, and Claude with a single character flag
- **File attachment support**: Process images, PDFs, and text files alongside your prompts
- **System instructions**: Define custom system-level instructions to guide model behavior
- **Configurable parameters**: Control temperature, top-p, top-k, and other generation parameters
- **Automatic file handling**: Handles base64 encoding and provider-specific file upload requirements
- **Privacy-focused**: Standard settings minimize data retention across all providers
  - OpenAI: Opts out of data storage for training, auto-deletes uploaded files
  - Gemini: Disables caching to prevent data retention
  - Claude: Configures privacy-preserving settings
- **Comprehensive error handling**: Clear error messages with specific exit codes
- **Type-safe**: Uses Python enums and type hints for better code reliability
- **Logging**: Structured logging with appropriate severity levels

## Installation

### Prerequisites

- Python 3.7 or higher
- API keys from the providers you wish to use

### Setup

1. Clone or download this repository

2. Install required dependencies:
```bash
pip install -r requirements.txt
```

3. Create API key files in the project directory:
   - `openai-api.key` - containing your OpenAI API key
   - `gemini-api.key` - containing your Google Gemini API key
   - `claude-api.key` - containing your Anthropic Claude API key

   Each file should contain only the API key string with no extra whitespace.

4. Make the script executable (optional):
```bash
chmod +x msgModel.py
```

## Usage

### Basic Syntax

```bash
python msgModel.py -a <ai_provider> -p <prompt_file> [-t <max_tokens>] [-i <instruction_file>] [-f <binary_file>]
```

Or with long-form arguments:

```bash
python msgModel.py --ai-provider <provider> --prompt-file <file> [--max-tokens <num>] [--instruction-file <file>] [--binary-file <file>]
```

### Parameters

**Required Arguments:**

- **-a, --ai-provider <provider>**: Choose the LLM provider
  - `o` - OpenAI (GPT models)
  - `g` - Gemini (Google)
  - `c` - Claude (Anthropic)

- **-p, --prompt-file <file>**: Path to a text file containing your main prompt/question

**Optional Arguments:**

- **-t, --max-tokens <num>**: Maximum number of tokens to generate (default: 1000)

- **-i, --instruction-file <file>**: Path to a text file containing system instructions (persona, behavior guidelines)

- **-f, --binary-file <file>**: Path to an attachment (image, PDF, or text file)

- **--version**: Display the script version and exit

- **-h, --help**: Display help message with all available options

**Note:** Arguments can be provided in any order.

### Examples

**Simple text prompt with Gemini (using default max_tokens):**
```bash
python msgModel.py -a g -p random.prompt
```

**Text prompt with custom token limit:**
```bash
python msgModel.py -a c -p random.prompt -t 500
```

**With system instruction:**
```bash
python msgModel.py -a g -p random.prompt -i analyst.instruction
```

**Image analysis with GPT-4:**
```bash
python msgModel.py -a o -t 1000 -p describe_image.prompt -i analyst.instruction -f photo.jpg
```

**PDF document processing with Gemini:**
```bash
python msgModel.py -a g -t 2000 -p analyze_doc.prompt -i summarizer.instruction -f report.pdf
```

**Arguments in any order:**
```bash
python msgModel.py -p request.prompt -t 500 -a c -i expert.instruction
```

### Sample Files

Create instruction and prompt files as plain text. Examples:

**expert.instruction**:
```
You are a seasoned technology strategist and operator with decades across infrastructure, software, product, security, and enterprise IT.
```

**random.prompt**:
```
Summarize this report in no more than 5 sentences, to a national healthcare policy advisor.
```

## Configuration

All configuration options are defined at the top of `msgModel.py` in a single unified CONFIGURATION section. To customize behavior, modify these constants:

### API Configuration
- `OPENAI_API_KEY_FILE` - default: `'openai-api.key'`
- `GEMINI_API_KEY_FILE` - default: `'gemini-api.key'`
- `CLAUDE_API_KEY_FILE` - default: `'claude-api.key'`
- `OPENAI_URL`, `OPENAI_FILES_URL`, `GEMINI_URL`, `CLAUDE_URL` - API endpoints

### Model Selection
- `OPENAI_MODEL` - default: `"gpt-4o"`
- `GEMINI_MODEL` - default: `"gemini-2.5-pro"`
- `CLAUDE_MODEL` - default: `"claude-sonnet-4-20250514"`

### OpenAI Parameters
- `OPENAI_TEMPERATURE` - default: `1.0`
- `OPENAI_TOP_P` - default: `1.0`
- `OPENAI_N` - default: `1`

### Gemini Parameters
- `GEMINI_TEMPERATURE` - default: `1.0`
- `GEMINI_TOP_P` - default: `0.95`
- `GEMINI_TOP_K` - default: `40`
- `GEMINI_CANDIDATE_COUNT` - default: `1`
- `GEMINI_SAFETY_THRESHOLD` - default: `"BLOCK_NONE"`
- `GEMINI_API_VERSION` - default: `"v1beta"`

### Claude Parameters
- `CLAUDE_TEMPERATURE` - default: `1.0`
- `CLAUDE_TOP_P` - default: `0.95`
- `CLAUDE_TOP_K` - default: `40`

### Privacy and Data Retention Settings
The script is configured by default to minimize data retention across all providers:

- `OPENAI_STORE_DATA` - default: `False`
  - When `False`, prevents OpenAI from using your data for model training
  - API requests include `"store": false` parameter
  
- `OPENAI_DELETE_FILES_AFTER_USE` - default: `True`
  - When `True`, automatically deletes uploaded files (PDFs) from OpenAI's servers immediately after processing
  - Ensures no file data persists on OpenAI's infrastructure
  
- `CLAUDE_CACHE_CONTROL` - default: `False`
  - When `False`, disables prompt caching to avoid data retention
  - Adds privacy-mode metadata to requests
  
- `GEMINI_CACHE_CONTROL` - default: `False`
  - When `False`, disables caching for privacy

### Default Values
- `DEFAULT_MAX_TOKENS` - default: `1000`
  - Used when the `-t` argument is not provided
  - Controls the maximum response length for all providers

**Privacy Note**: These settings prioritize data privacy by default. The script will display privacy settings at the end of each execution to confirm which protections are active.

**Note**: All configuration values are required and used explicitly throughout the script. The functions do not assume any default values - all parameters are passed from the configuration constants.

## Architecture and Code Quality

The script follows Python best practices:

- **Flexible argument parsing**: Named arguments with prefix flags (`-a`, `-p`, `-t`, `-i`, `-f`) that can be provided in any order
- **Modular design**: Separate functions for each provider's API calls
- **Type safety**: Comprehensive type hints using Python's `typing` module
- **Enumerations**: `AIProvider` and `ExitCode` enums for type-safe constants
- **Input validation**: Validates file existence and parameter ranges before processing
- **Structured logging**: Uses Python's `logging` module instead of print statements
- **Error handling**: Specific exception handling with meaningful error messages
- **Exit codes**: Different exit codes for different error conditions:
  - `0`: Success
  - `1`: Invalid arguments
  - `2`: File not found
  - `3`: API error
  - `4`: Authentication error
- **Documentation**: Comprehensive docstrings for all functions
- **Privacy by default**: Data retention minimization built into the core logic
- **Sensible defaults**: Optional arguments have reasonable defaults (e.g., `max_tokens=1000`)

## Supported File Types

- **Images**: JPEG, PNG, GIF, WebP (automatically converted to base64)
- **PDFs**: Uploaded and processed by supported providers
- **Text files**: Decoded and included directly in prompts
- **Other binary files**: Noted but may not be fully processed

## Output

The script outputs:
- The generated response text (for OpenAI, includes extracted response before full JSON)
- The complete API response as JSON to stdout
- Status messages, errors, and privacy information to stderr
- Exit code 0 on success, non-zero on failure (see Exit Codes above)

## Error Handling

The script provides detailed error messages for common issues:

- **Invalid arguments**: Clear usage information with provider options
- **File not found**: Specific file type and path in error message
- **API errors**: HTTP status code and response details
- **Authentication errors**: Guidance on API key file setup
- **Invalid max_tokens**: Range validation with helpful warnings

All errors are logged to stderr with appropriate severity levels (ERROR, WARNING, INFO).

## API Rate Limits

Be aware of rate limits for each provider:
- **OpenAI**: Varies by plan and model
- **Gemini**: Check Google AI Studio for current limits
- **Claude**: Varies by plan tier

## Security Notes

- Keep your API key files secure and never commit them to version control
- Add `*.key` to your `.gitignore` file
- API keys grant access to paid services - treat them like passwords
- Consider using environment variables for production deployments

## Privacy and Data Protection

This script is designed with privacy as a priority:

### Data Retention Minimization

**OpenAI:**
- All API requests include `"store": false` to opt out of data retention for model training
- Uploaded files (PDFs) are automatically deleted from OpenAI's servers immediately after processing
- No prompt data or file content persists beyond the immediate API call
- Privacy status is logged to stderr after each execution

**Claude (Anthropic):**
- Privacy-mode metadata is added to requests when caching is disabled
- Caching is disabled by default to prevent data retention
- According to Anthropic's policies, data sent to the API is not used for training

**Gemini (Google):**
- Caching is disabled by default
- Check Google's current data retention policies for Gemini API

### Verifying Privacy Settings

After each script execution, check the stderr output for:
```
=== Privacy Settings ===
OpenAI - Data retention opt-out: True
OpenAI - Auto-delete uploaded files: True
```

### Customizing Privacy Settings

To modify privacy behavior, edit the configuration constants at the top of `msgModel.py`:
- Set `OPENAI_STORE_DATA = True` if you want OpenAI to retain data for model improvement
- Set `OPENAI_DELETE_FILES_AFTER_USE = False` if you want to manually manage uploaded files
- Set `CLAUDE_CACHE_CONTROL = True` or `GEMINI_CACHE_CONTROL = True` to enable caching

**Important**: Even with these protections, be mindful of:
- Provider terms of service and privacy policies
- Applicable data protection regulations (GDPR, CCPA, etc.)
- Sensitive data - avoid sending personal, confidential, or regulated information unless absolutely necessary

## License

This project is provided as-is for educational and development purposes.

## Contributing

Feel free to submit issues or pull requests to improve functionality or add support for additional providers.

## Support

For issues related to:
- **Script functionality**: Check error messages and verify API key configuration
- **API-specific issues**: Consult the respective provider's documentation:
  - [OpenAI API Docs](https://platform.openai.com/docs)
  - [Gemini API Docs](https://ai.google.dev/docs)
  - [Claude API Docs](https://docs.anthropic.com)