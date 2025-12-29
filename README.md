# msgmodel

[![PyPI version](https://badge.fury.io/py/msgmodel.svg)](https://badge.fury.io/py/msgmodel)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A unified Python library and CLI for interacting with multiple Large Language Model (LLM) providers with a **simple, consistent syntax**.

## Overview

`msgmodel` provides both a **Python library** and a **command-line interface** to interact with major LLM providers:
- **OpenAI** (GPT models)
- **Google Gemini**
- **Anthropic Claude**

### Privacy by Default

**msgmodel takes a privacy-preserving stance by default.** Where providers offer opt-out mechanisms, we use them automatically. Where they don't, we document the limitations honestly.

| What msgmodel controls | What msgmodel cannot control |
|------------------------|------------------------------|
| ✅ Sends `X-OpenAI-No-Store` header automatically | ❌ OpenAI ZDR eligibility (requires account approval) |
| ✅ Uses inline base64 encoding (no server-side file uploads) | ❌ Gemini tier detection (paid vs. free) |
| ✅ Stateless design (we retain nothing) | ❌ Provider-side retention policies |
| ✅ No parameters to accidentally enable retention | ❌ Provider terms of service changes |

**You don't need to configure anything for privacy** — msgmodel's defaults are already privacy-preserving. However, **provider-level guarantees depend on your account status and tier.** See the [Data Retention & Privacy](#data-retention--privacy) section for details.

## Features

- **Unified API**: Single `query()` and `stream()` functions work with all providers
- **Library & CLI**: Use as a Python module or command-line tool
- **Streaming support**: Stream responses in real-time
- **File attachments**: Process images, PDFs, and text files with in-memory BytesIO
- **Flexible configuration**: Dataclass-based configs with sensible defaults
- **Multiple API key sources**: Direct parameter, environment variable, or key file
- **Exception-based error handling**: Clean errors, no `sys.exit()` in library code
- **Type-safe**: Full type hints throughout
- **Stateless design**: msgmodel never retains your data; all processing is ephemeral

## Installation

### From PyPI (Recommended)

```bash
pip install msgmodel
```

### From Source

```bash
# Clone the repository
git clone https://github.com/LeoooDias/msgmodel.git
cd msgmodel

# Install the package
pip install -e .

# Or with development dependencies
pip install -e ".[dev]"
```

### Prerequisites

- Python 3.10 or higher
- API keys from the providers you wish to use

## Quick Start

### As a Library

```python
from msgmodel import query, stream

# Simple query (uses OPENAI_API_KEY env var)
response = query("openai", "What is Python?")
print(response.text)

# With explicit API key
response = query("gemini", "Hello!", api_key="your-api-key")

# Streaming
for chunk in stream("openai", "Tell me a story"):
    print(chunk, end="", flush=True)

# With file attachment (in-memory BytesIO only)
import io
file_obj = io.BytesIO(your_binary_data)
response = query("gemini", "Describe this image", file_like=file_obj, filename="photo.jpg")

# With custom configuration
from msgmodel import OpenAIConfig

config = OpenAIConfig(model="gpt-4o-mini", temperature=0.7, max_tokens=2000)
response = query("openai", "Write a poem", config=config)
```

### As a CLI

```bash
# Basic usage
python -m msgmodel -p openai "What is Python?"

# Using shorthand provider codes
python -m msgmodel -p g "Hello, Gemini!"    # g = gemini
python -m msgmodel -p o "Hello, OpenAI!"    # o = openai
python -m msgmodel -p c "Hello, Claude!"    # c = claude/anthropic

# With streaming
python -m msgmodel -p openai "Tell me a story" --stream

# From a file
python -m msgmodel -p gemini -f prompt.txt

# With system instruction
python -m msgmodel -p claude "Analyze this" -i "You are a data analyst"

# With file attachment (base64 inline)
python -m msgmodel -p gemini "Describe this" -b image.jpg

# Custom parameters
python -m msgmodel -p openai "Hello" -m gpt-4o-mini -t 500 --temperature 0.7

# Get full JSON response instead of just text
python -m msgmodel -p openai "Hello" --json

# Verbose output (shows model, provider, token usage)
python -m msgmodel -p openai "Hello" -v
```

## API Key Configuration

API keys can be provided in three ways (in order of priority):

1. **Direct parameter**: `query("openai", "Hello", api_key="sk-...")`
2. **Environment variable**:
   - `OPENAI_API_KEY` for OpenAI
   - `GOOGLE_API_KEY` for Gemini
   - `ANTHROPIC_API_KEY` for Claude/Anthropic
3. **Key file** in current directory:
   - `openai-api.key`
   - `gemini-api.key`
   - `anthropic-api.key`

## Configuration

Each provider has its own configuration dataclass with sensible defaults:

```python
from msgmodel import OpenAIConfig, GeminiConfig, AnthropicConfig

# OpenAI configuration
openai_config = OpenAIConfig(
    model="gpt-4o",           # Model to use
    temperature=1.0,          # Sampling temperature
    top_p=1.0,                # Nucleus sampling
    max_tokens=1000,          # Max output tokens
)

# Gemini configuration
gemini_config = GeminiConfig(
    model="gemini-2.5-flash",
    temperature=1.0,
    top_p=0.95,
    top_k=40,
    safety_threshold="BLOCK_NONE",
)

# Anthropic/Claude configuration
anthropic_config = AnthropicConfig(
    model="claude-haiku-4-5-20251001",  # Default; also: claude-sonnet-4-20250514
    temperature=1.0,
    top_p=1.0,
    max_tokens=1000,
)
```

## Data Retention & Privacy

**msgmodel is stateless** — it never retains your data. All processing is ephemeral.

**Provider behavior varies** — and is ultimately outside our control. This section documents what msgmodel does by default and what depends on your provider account.

### OpenAI

When using OpenAI:

- **Training opt-out**: OpenAI does **not** use API data for model training (this is standard policy for all API users since March 2023)
- **Data storage**: By default, OpenAI may retain API data for up to 30 days for abuse monitoring. The `X-OpenAI-No-Store` header is sent to request zero storage, but **Zero Data Retention (ZDR) requires separate eligibility** from OpenAI
- **File handling**: All files are base64-encoded and embedded inline in prompts—no server-side uploads

**Important**: Training opt-out is automatic for all API users. However, if you need **zero data storage** (not just no training), you must be ZDR-eligible with OpenAI. Review [OpenAI's data usage policy](https://platform.openai.com/docs/models/how-we-use-your-data) and [ZDR documentation](https://platform.openai.com/docs/guides/zero-data-retention).

```python
from msgmodel import query

response = query("openai", "Your prompt here")
# Training opt-out: automatic | ZDR header: sent (eligibility required)
```

### Google Gemini

Google Gemini's data handling depends entirely on your account tier. **msgmodel cannot detect or control which tier you're on.**

| Tier | Training Opt-Out | Data Retention |
|------|------------------|----------------|
| **Paid** (Cloud Billing) | ✅ Yes | ~24-72 hours (abuse monitoring only) |
| **Free** | ❌ No | Data may be used for model training |

**What msgmodel does**: Uses inline base64 encoding for files (no server-side uploads).

**What msgmodel cannot do**: Detect your tier or change Google's data handling policies.

**If privacy matters for your use case**: Verify you have Google Cloud Billing enabled with paid API quota. Free tier users should assume their data may be used for training.

```python
from msgmodel import query

# Data handling depends entirely on YOUR Google account tier
response = query("gemini", "Your prompt here")
```

**Learn more**: [Google Gemini API Terms](https://ai.google.dev/gemini-api/terms)

### Anthropic Claude

When using Anthropic Claude:

- **Default behavior**: Anthropic does not use API data for model training by default
- **Data retention**: Data may be retained temporarily for safety monitoring and abuse prevention
- **File handling**: Base64-encoded inline embedding

```python
from msgmodel import query

response = query("claude", "Your prompt here")
# or: query("anthropic", ...) or query("c", ...)
```

**Learn more**: [Anthropic Privacy Policy](https://www.anthropic.com/legal/privacy)

### Summary

| Provider | What msgmodel does | Training Opt-Out | Data Retention |
|----------|-------------------|------------------|----------------|
| **OpenAI** | Sends `X-OpenAI-No-Store` header | ✅ Automatic (API policy) | ~30 days; ZDR requires eligibility |
| **Gemini** | Inline file encoding only | ⚠️ Depends on YOUR tier | Paid: ~24-72h / Free: training |
| **Anthropic** | Standard API calls | ✅ Default (API policy) | Temporary (safety monitoring) |

### Limitations

msgmodel cannot:
- Verify your OpenAI ZDR eligibility
- Detect your Gemini account tier
- Override provider terms of service
- Guarantee provider policy compliance

**For maximum privacy**: Verify your account status directly with each provider. msgmodel sends all available privacy-preserving signals, but enforcement is provider-side.

## File Uploads

### The BytesIO-Only Approach

All file uploads in msgmodel v3.2.0+ use **in-memory BytesIO objects** with base64 inline encoding:

```python
import io
from msgmodel import query

# Read file into memory
with open("document.pdf", "rb") as f:
    file_data = f.read()

# Create BytesIO object
file_obj = io.BytesIO(file_data)

# Query with file
response = query(
    "openai",
    "Summarize this document",
    file_like=file_obj,
    filename="document.pdf"  # Enables MIME type detection
)
```

**Why BytesIO?**
- Stateless operation—each request is completely independent
- No server-side file uploads (Files API not used)
- Files are base64-encoded inline in prompts

**File Size Limits**
- **OpenAI**: ~15-20MB practical limit (base64 overhead + token limits)
- **Gemini**: ~22MB practical limit (base64 overhead + token limits)
- **Anthropic**: ~20MB practical limit (base64 overhead + token limits)

If API returns a size-related error, the file exceeds practical limits for that provider.

## Error Handling

The library uses exceptions instead of `sys.exit()`:

```python
from msgmodel import query, MsgModelError, AuthenticationError, APIError

try:
    response = query("openai", "Hello")
except AuthenticationError as e:
    print(f"API key issue: {e}")
except APIError as e:
    print(f"API call failed: {e}")
    print(f"Status code: {e.status_code}")
except MsgModelError as e:
    print(f"General error: {e}")
```

## Response Object

The `query()` function returns an `LLMResponse` object:

```python
response = query("openai", "Hello")

print(response.text)          # The generated text
print(response.model)         # Model used (e.g., "gpt-4o")
print(response.provider)      # Provider name (e.g., "openai")
print(response.usage)         # Token usage dict (if available)
print(response.raw_response)  # Complete API response
```

## Project Structure

```
msgmodel/
├── msgmodel/                    # Python package
│   ├── __init__.py              # Public API exports
│   ├── __main__.py              # CLI entry point
│   ├── core.py                  # Core query/stream functions
│   ├── config.py                # Configuration dataclasses
│   ├── exceptions.py            # Custom exceptions
│   ├── py.typed                 # PEP 561 marker for typed package
│   └── providers/               # Provider implementations
│       ├── __init__.py
│       ├── openai.py
│       └── gemini.py
├── tests/                       # Test suite
│   ├── test_config.py
│   ├── test_core.py
│   └── test_exceptions.py
├── pyproject.toml               # Package configuration
├── LICENSE                      # MIT License
├── MANIFEST.in                  # Distribution manifest
├── requirements.txt             # Dependencies
└── README.md
```

## CLI Usage

After installation, the `msgmodel` command is available:

```bash
# Basic usage
msgmodel -p openai "What is Python?"

# Or using python -m
python -m msgmodel -p openai "What is Python?"

# Provider shortcuts: o=openai, g=gemini
msgmodel -p g "Hello, Gemini!"

# With streaming
msgmodel -p openai "Tell me a story" --stream

# From a file
msgmodel -p gemini -f prompt.txt
```

## Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests
pytest

# Run with coverage
pytest --cov=msgmodel
```

## Building & Publishing

```bash
# Install build tools
pip install build twine

# Build the package
python -m build

# Check the distribution
twine check dist/*

# Upload to PyPI (requires PyPI account)
twine upload dist/*

# Upload to TestPyPI first (recommended)
twine upload --repository testpypi dist/*
```

## License

MIT License - see [LICENSE](LICENSE) for details.

## Author

Leo Dias

