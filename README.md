# msgmodel

[![PyPI version](https://badge.fury.io/py/msgmodel.svg)](https://badge.fury.io/py/msgmodel)
[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A unified Python library and CLI for interacting with multiple Large Language Model (LLM) providers.

## Overview

`msgmodel` provides both a **Python library** and a **command-line interface** to interact with three major LLM providers:
- **OpenAI** (GPT models)
- **Google Gemini**
- **Anthropic Claude**

Use it as a library in your Python projects or as a CLI tool for quick interactions.

## Features

- **Unified API**: Single `query()` and `stream()` functions work with all providers
- **Library & CLI**: Use as a Python module or command-line tool
- **Streaming support**: Stream responses in real-time
- **File attachments**: Process images, PDFs, and text files with your prompts
- **Flexible configuration**: Dataclass-based configs with sensible defaults
- **Multiple API key sources**: Direct parameter, environment variable, or key file
- **Exception-based error handling**: Clean errors, no `sys.exit()` in library code
- **Type-safe**: Full type hints throughout
- **Privacy-focused**: Minimal data retention settings by default

## Installation

### From PyPI (Recommended)

```bash
# Basic installation
pip install msgmodel

# With Claude support
pip install msgmodel[claude]

# With all optional dependencies
pip install msgmodel[all]
```

### From Source

```bash
# Clone the repository
git clone https://github.com/LeoooDias/msgModel.git
cd msgModel

# Install the package
pip install -e .

# Or with Claude support
pip install -e ".[claude]"

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
for chunk in stream("claude", "Tell me a story"):
    print(chunk, end="", flush=True)

# With file attachment
response = query("gemini", "Describe this image", file_path="photo.jpg")

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
python -m msgmodel -p g "Hello, Gemini!"  # g = gemini
python -m msgmodel -p c "Hello, Claude!"  # c = claude

# With streaming
python -m msgmodel -p openai "Tell me a story" --stream

# From a file
python -m msgmodel -p gemini -f prompt.txt

# With system instruction
python -m msgmodel -p claude "Analyze this" -i "You are a data analyst"

# With file attachment
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
   - `GEMINI_API_KEY` for Gemini
   - `ANTHROPIC_API_KEY` for Claude
3. **Key file** in current directory:
   - `openai-api.key`
   - `gemini-api.key`
   - `claude-api.key`

## Configuration

Each provider has its own configuration dataclass with sensible defaults:

```python
from msgmodel import OpenAIConfig, GeminiConfig, ClaudeConfig

# OpenAI configuration
openai_config = OpenAIConfig(
    model="gpt-4o",           # Model to use
    temperature=1.0,           # Sampling temperature
    top_p=1.0,                 # Nucleus sampling
    max_tokens=1000,           # Max output tokens
    store_data=False,          # Don't store data for training
)

# Gemini configuration
gemini_config = GeminiConfig(
    model="gemini-2.5-flash",
    temperature=1.0,
    top_p=0.95,
    top_k=40,
    safety_threshold="BLOCK_NONE",
)

# Claude configuration
claude_config = ClaudeConfig(
    model="claude-sonnet-4-20250514",
    temperature=1.0,
    top_p=0.95,
    top_k=40,
)
```

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
msgModel/
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
│       ├── gemini.py
│       └── claude.py
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

# Provider shortcuts: o=openai, g=gemini, c=claude
msgmodel -p g "Hello, Gemini!"
msgmodel -p c "Hello, Claude!"

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
  
