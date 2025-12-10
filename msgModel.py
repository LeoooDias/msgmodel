#!/usr/bin/env python3
# Shebang line allows this script to be executed directly on Unix-like systems

"""
msgModel.py
A unified LLM API script supporting OpenAI, Gemini, and Claude.

This script provides a single interface to interact with three major LLM providers:
- OpenAI (GPT models)
- Google Gemini
- Anthropic Claude

Usage: python msgModel.py -a <ai_provider> -p <prompt_file> [-t <max_tokens>] [-i <instruction_file>] [-f <binary_file>]

Required arguments:
    -a <ai_provider>          AI provider: 'o' (OpenAI), 'g' (Gemini), 'c' (Claude)
    -p <prompt_file>        Path to file containing the user prompt

Optional arguments:
    -t <max_tokens>         Maximum number of tokens to generate (default: 1000)
    -i <instruction_file>   Path to file containing system instructions
    -f <binary_file>        Path to binary file (image, PDF, etc.)

Examples:
    python msgModel.py -a g -p random.prompt
    python msgModel.py -a o -t 1000 -p describe.prompt -i analyst.instruction -f photo.jpg
    python msgModel.py -p request.prompt -t 500 -a c -i max.instruction
"""

__version__ = "1.0.0"
__author__ = "Leo Dias"

# ============================================================================
# CONFIGURATION
# ============================================================================
"""
Configuration constants for the script.

All configuration options are defined here. These control API endpoints,
model selection, generation parameters, and privacy settings.

Customize these values as needed for your use case.
"""

# API key files (must exist in working directory)
# These files should contain only the API key string, with no extra whitespace
OPENAI_API_KEY_FILE = 'openai-api.key'
GEMINI_API_KEY_FILE = 'gemini-api.key'
CLAUDE_API_KEY_FILE = 'claude-api.key'

# API URLs - Base endpoints for each LLM provider
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENAI_FILES_URL = "https://api.openai.com/v1/files"
GEMINI_URL = "https://generativelanguage.googleapis.com"
CLAUDE_URL = "https://api.anthropic.com"

# Model selection - Specifies which specific model variant to use from each provider
# OpenAI - See options at https://platform.openai.com/docs/models
OPENAI_MODEL = "gpt-5-nano"                 
# Gemini - See options at https://ai.google.dev/gemini-api/docs/models
GEMINI_MODEL = "gemini-2.5-flash"             
# Claude - See options at https://platform.claude.com/docs/en/about-claude/models/overview 
CLAUDE_MODEL = "claude-sonnet-4-20250514"   

# OpenAI specific settings
OPENAI_TEMPERATURE = 1.0
OPENAI_TOP_P = 1.0
OPENAI_N = 1

# Gemini specific settings
GEMINI_TEMPERATURE = 1.0
GEMINI_TOP_P = 0.95
GEMINI_TOP_K = 40
GEMINI_CANDIDATE_COUNT = 1
GEMINI_SAFETY_THRESHOLD = "BLOCK_NONE"
GEMINI_API_VERSION = "v1beta"

# Claude specific settings
CLAUDE_TEMPERATURE = 1.0
CLAUDE_TOP_P = 0.95
CLAUDE_TOP_K = 40

# Privacy and data retention settings
OPENAI_STORE_DATA = False
OPENAI_DELETE_FILES_AFTER_USE = True
CLAUDE_CACHE_CONTROL = False
GEMINI_CACHE_CONTROL = False

# Default values for optional arguments
DEFAULT_MAX_TOKENS = 1000  # Default maximum tokens if not specified as an argument

# File encoding
FILE_ENCODING = 'utf-8'  # Standard encoding for text files

# MIME type constants
MIME_TYPE_JSON = 'application/json'
MIME_TYPE_PDF = 'application/pdf'
MIME_TYPE_OCTET_STREAM = 'application/octet-stream'

# ============================================================================
# IMPORTS
# ============================================================================
import argparse                 #For parsing command-line arguments
import requests                 #For making HTTP API calls to LLM providers
import json                     #For encoding/decoding JSON payloads
import sys                      #For system operations and exiting
import base64                   #For encoding/decoding binary data (e.g., images, PDFs)
import mimetypes                #For detecting file types from file extensions
import logging                  #For logging messages
from datetime import datetime   #For timestamping output files
from pathlib import Path        #For modern path operations
from typing import Optional, Dict, Any, List    #For type hints to improve code readability and IDE support
from enum import Enum                           #For defining enumerated constants


# ============================================================================
# LOGGING CONFIGURATION
# ============================================================================
# Configure logging at module level
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s',
    stream=sys.stderr
)
logger = logging.getLogger(__name__)


# ============================================================================
# EXIT CODES
# ============================================================================
class ExitCode(Enum):
    """Exit codes for different error conditions."""
    SUCCESS = 0
    INVALID_ARGUMENTS = 1
    FILE_NOT_FOUND = 2
    API_ERROR = 3
    AUTHENTICATION_ERROR = 4
    GENERAL_ERROR = 5


# ============================================================================
# AI PROVIDER ENUM
# ============================================================================
class AIProvider(Enum):
    """Supported AI providers."""
    OPENAI = 'o'
    GEMINI = 'g'
    CLAUDE = 'c'
    
    @classmethod
    def from_string(cls, value: str) -> 'AIProvider':
        """
        Convert string to AIProvider enum.
        
        Args:
            value: Single character string ('o', 'g', or 'c')
            
        Returns:
            AIProvider enum member
            
        Raises:
            ValueError: If the value is not a valid provider code
        """
        value = value.lower()
        for provider in cls:
            if provider.value == value:
                return provider
        raise ValueError(
            f"Invalid AI provider '{value}'. "
            f"Use 'o' (OpenAI), 'g' (Gemini), or 'c' (Claude)"
        )


# ============================================================================
# INPUT VALIDATION
# ============================================================================
def validate_max_tokens(max_tokens: int) -> None:
    """
    Validate that max_tokens is within reasonable bounds.
    
    Args:
        max_tokens: The maximum number of tokens to generate
        
    Raises:
        ValueError: If max_tokens is not within valid range
    """
    if max_tokens < 1:
        raise ValueError("max_tokens must be at least 1")
    if max_tokens > 1000000:
        logger.warning(f"max_tokens={max_tokens} is very large and may cause issues")


def validate_file_exists(file_path: str, file_description: str) -> None:
    """
    Validate that a file exists.
    
    Args:
        file_path: Path to the file to validate
        file_description: Human-readable description of the file (for error messages)
        
    Raises:
        FileNotFoundError: If the file does not exist
    """
    if not Path(file_path).exists():
        raise FileNotFoundError(f"{file_description} not found: {file_path}")


def parse_arguments() -> Dict[str, Any]:
    """
    Parse command-line arguments using argparse.
    
    Returns:
        Dict containing parsed arguments: ai_provider, max_tokens, prompt_file,
        instruction_file (optional), binary_file (optional)
    """
    parser = argparse.ArgumentParser(
        description='Unified LLM API script supporting OpenAI, Gemini, and Claude.',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog='''
Examples:
  %(prog)s -a g -p random.prompt
  %(prog)s -a o -t 1000 -p describe.prompt -i analyst.instruction -f photo.jpg
  %(prog)s -p request.prompt -t 500 -a c -i max.instruction
'''
    )
    
    parser.add_argument(
        '-a', '--ai-provider',
        required=True,
        choices=['o', 'g', 'c'],
        help="AI provider: 'o' (OpenAI), 'g' (Gemini), 'c' (Claude)"
    )
    
    parser.add_argument(
        '-p', '--prompt-file',
        required=True,
        help='Path to file containing the user prompt'
    )
    
    parser.add_argument(
        '-t', '--max-tokens',
        type=int,
        default=DEFAULT_MAX_TOKENS,
        help=f'Maximum number of tokens to generate (default: {DEFAULT_MAX_TOKENS})'
    )
    
    parser.add_argument(
        '-i', '--instruction-file',
        help='Path to file containing system instructions'
    )
    
    parser.add_argument(
        '-f', '--binary-file',
        help='Path to binary file (image, PDF, etc.)'
    )
    
    parser.add_argument(
        '--version',
        action='version',
        version=f'%(prog)s {__version__}'
    )
    
    args = parser.parse_args()
    
    return {
        'ai_provider': args.ai_provider,
        'max_tokens': args.max_tokens,
        'prompt_file': args.prompt_file,
        'instruction_file': args.instruction_file,
        'binary_file': args.binary_file
    }


# ============================================================================
# OpenAI Functions
# ============================================================================
def upload_file_openai(api_key: str, file_path: str, purpose: str = "assistants") -> str:
    """
    Upload a file to OpenAI Files API and return file_id.
    
    Args:
        api_key: OpenAI API authentication key
        file_path: Path to the file to upload
        purpose: Purpose of the upload ("assistants" is used for file analysis)
    
    Returns:
        str: The file_id assigned by OpenAI
    
    Raises:
        requests.HTTPError: If the upload fails
    """
    url = OPENAI_FILES_URL
    headers = {"Authorization": f"Bearer {api_key}"}
    
    with open(file_path, "rb") as f:
        files = {"file": (Path(file_path).name, f)}
        data = {"purpose": purpose}
        resp = requests.post(url, headers=headers, files=files, data=data)
    
    if not resp.ok:
        logger.error(f"File upload failed {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    
    payload = resp.json()
    return payload.get("id")


def delete_file_openai(api_key: str, file_id: str) -> bool:
    """
    Delete a file from OpenAI Files API to ensure data privacy.
    
    Args:
        api_key: OpenAI API authentication key
        file_id: The file ID to delete
    
    Returns:
        bool: True if deletion was successful, False otherwise
    """
    url = f"{OPENAI_FILES_URL}/{file_id}"
    headers = {"Authorization": f"Bearer {api_key}"}
    
    try:
        resp = requests.delete(url, headers=headers)
        if resp.ok:
            return True
        else:
            logger.warning(
                f"Failed to delete file {file_id}: "
                f"{resp.status_code} - {resp.text}"
            )
            return False
    except requests.RequestException as e:
        logger.warning(f"Request exception while deleting file {file_id}: {e}")
        return False
    except Exception as e:
        logger.warning(f"Unexpected exception while deleting file {file_id}: {e}")
        return False


def call_openai_api(
    api_key: str,
    user_prompt: str,
    max_tokens: int,
    system_instruction: Optional[str],
    file_data: Optional[Dict[str, str]],
    temperature: float,
    top_p: float,
    n: int,
    model: str
) -> Dict[str, Any]:
    """
    Make an API call to OpenAI using the Responses API.
    
    Args:
        api_key: OpenAI API key for authentication
        user_prompt: The main text prompt from the user
        max_tokens: Maximum number of tokens to generate in the response
        system_instruction: Optional system-level instructions
        file_data: Optional dictionary containing file information
        temperature: Controls randomness in the output
        top_p: Nucleus sampling parameter
        n: Number of completions to generate
        model: Model identifier to use
    
    Returns:
        Dict containing the API response
        
    Raises:
        requests.HTTPError: If the API request fails
    """
    url = OPENAI_URL
    content: List[Dict[str, Any]] = []

    if file_data:
        mime_type = file_data["mime_type"]
        encoded_data = file_data.get("data", "")
        filename = file_data.get("filename", "input.bin")
        file_id = file_data.get("file_id")

        if mime_type.startswith("image/"):
            content.append({
                "type": "input_image",
                "image_url": f"data:{mime_type};base64,{encoded_data}"
            })
        elif mime_type == MIME_TYPE_PDF:
            if not file_id:
                raise ValueError("PDF provided without uploaded file_id")
            content.append({
                "type": "input_file",
                "file_id": file_id,
            })
        elif mime_type.startswith("text/"):
            try:
                decoded_text = base64.b64decode(encoded_data).decode("utf-8", errors="ignore")
            except Exception:
                decoded_text = ""
            if decoded_text.strip():
                content.append({
                    "type": "input_text",
                    "text": f"(Contents of {filename}):\n\n{decoded_text}"
                })
        else:
            content.append({
                "type": "input_text",
                "text": (
                    f"[Note: A file named '{filename}' with MIME type '{mime_type}' "
                    f"was provided. You may not be able to read it directly, but you "
                    f"can still respond based on the description and prompt.]"
                )
            })

    content.append({
        "type": "input_text",
        "text": user_prompt
    })

    input_items: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": content
        }
    ]

    payload: Dict[str, Any] = {
        "model": model,
        "input": input_items,
        "max_output_tokens": max_tokens,
        "temperature": temperature,
        "top_p": top_p,
    }

    if system_instruction:
        payload["instructions"] = system_instruction
    
    if not OPENAI_STORE_DATA:
        payload["store"] = False

    headers = {
        "Content-Type": MIME_TYPE_JSON,
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if not response.ok:
        logger.error(f"OpenAI API error {response.status_code}: {response.text}")
        response.raise_for_status()

    return response.json()


# ============================================================================
# Gemini Functions
# ============================================================================
def call_gemini_api(
    api_key: str,
    gemini_user_prompt: str,
    gemini_max_tokens: int,
    gemini_system_instruction: Optional[Dict[str, Any]],
    gemini_inline_data: Optional[Dict[str, str]],
    gemini_temperature: float,
    gemini_top_p: float,
    gemini_top_k: int,
    gemini_candidate_count: int,
    gemini_safety_threshold: str,
    gemini_api_version: str,
    model: str
) -> Dict[str, Any]:
    """
    Make an API call to Google Gemini.
    
    Args:
        api_key: Google API key for Gemini
        gemini_user_prompt: The user's text prompt
        gemini_max_tokens: Maximum tokens to generate
        gemini_system_instruction: Optional system instruction as a dict
        gemini_inline_data: Optional file data dict
        gemini_temperature: Sampling temperature
        gemini_top_p: Nucleus sampling parameter
        gemini_top_k: Top-k sampling parameter
        gemini_candidate_count: Number of response candidates to generate
        gemini_safety_threshold: Content safety filtering level
        gemini_api_version: API version
        model: Model identifier
    
    Returns:
        Dict containing the API response
        
    Raises:
        requests.HTTPError: If the API request fails
    """
    url = f"{GEMINI_URL}/{gemini_api_version}/models/{model}:generateContent?key={api_key}"
    
    parts: List[Dict[str, Any]] = [{"text": gemini_user_prompt}]
    
    if gemini_inline_data:
        filtered_inline_data = {
            "mime_type": gemini_inline_data["mime_type"],
            "data": gemini_inline_data["data"]
        }
        parts.append({"inline_data": filtered_inline_data})
    
    payload = {
        "contents": [
            {
                "parts": parts
            }
        ],
        "generationConfig": {
            "maxOutputTokens": gemini_max_tokens,
            "temperature": gemini_temperature,
            "topP": gemini_top_p,
            "topK": gemini_top_k,
            "candidateCount": gemini_candidate_count
        },
        "safetySettings": [
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": gemini_safety_threshold},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": gemini_safety_threshold},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": gemini_safety_threshold},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": gemini_safety_threshold}
        ]
    }
    
    if gemini_system_instruction:
        payload["systemInstruction"] = gemini_system_instruction
    
    headers = {
        "Content-Type": MIME_TYPE_JSON
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if not response.ok:
        logger.error(f"Gemini API error {response.status_code}: {response.text}")
        response.raise_for_status()
    
    return response.json()


# ============================================================================
# Claude Functions
# ============================================================================
def call_claude_api(
    api_key: str,
    user_prompt: str,
    max_tokens: int,
    system_instruction: Optional[str],
    inline_data: Optional[Dict[str, str]],
    temperature: float,
    top_p: float,
    top_k: int,
    model: str
) -> Dict[str, Any]:
    """
    Make an API call to Anthropic Claude.
    
    Args:
        api_key: Anthropic API key
        user_prompt: The user's text prompt
        max_tokens: Maximum tokens to generate
        system_instruction: Optional system-level instruction string
        inline_data: Optional file data dict
        temperature: Sampling temperature
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        model: Model identifier
    
    Returns:
        Dict containing the API response
        
    Raises:
        SystemExit: If the anthropic library is not installed
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        logger.error("anthropic package not installed. Install with: pip install anthropic")
        sys.exit(ExitCode.API_ERROR.value)
    
    client = Anthropic(api_key=api_key)
    
    content: List[Dict[str, Any]] = []
    
    if inline_data:
        mime_type = inline_data["mime_type"]
        data = inline_data["data"]
        
        if mime_type.startswith("image/"):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": data
                }
            })
        elif mime_type == MIME_TYPE_PDF:
            content.append({
                "type": "document",
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": data
                }
            })
    
    content.append({
        "type": "text",
        "text": user_prompt
    })
    
    messages = [
        {
            "role": "user",
            "content": content
        }
    ]
    
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k
    }
    
    if system_instruction:
        kwargs["system"] = system_instruction
    
    if not CLAUDE_CACHE_CONTROL:
        kwargs["metadata"] = {"user_id": "privacy-mode"}

    response = client.messages.create(**kwargs)
    
    return {
        "id": response.id,
        "model": response.model,
        "role": response.role,
        "content": [
            {
                "type": block.type,
                "text": block.text if hasattr(block, 'text') else None
            } for block in response.content
        ],
        "stop_reason": response.stop_reason,
        "usage": {
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
    }


# ============================================================================
# Main Execution
# ============================================================================
def main() -> None:
    """Main entry point for the script."""
    
    # Parse command-line arguments
    try:
        args = parse_arguments()
    except ValueError as e:
        logger.error(str(e))
        logger.error(
            "Usage: python msgModel.py -a <ai_provider> -p <prompt_file> "
            "[-t <max_tokens>] [-i <instruction_file>] [-f <binary_file>]"
        )
        logger.error(
            "  -a: AI provider ('o' for OpenAI, 'g' for Gemini, 'c' for Claude) [REQUIRED]"
        )
        logger.error("  -p: Path to user prompt file [REQUIRED]")
        logger.error(f"  -t: Maximum tokens to generate (default: {DEFAULT_MAX_TOKENS}) [OPTIONAL]")
        logger.error("  -i: Path to system instruction file [OPTIONAL]")
        logger.error("  -f: Path to binary file - image, PDF, etc. [OPTIONAL]")
        sys.exit(ExitCode.INVALID_ARGUMENTS.value)
    
    # Validate AI provider
    try:
        ai_provider = AIProvider.from_string(args['ai_provider'])
    except ValueError as e:
        logger.error(str(e))
        sys.exit(ExitCode.INVALID_ARGUMENTS.value)
    
    # Validate max_tokens
    max_tokens = args['max_tokens']
    try:
        validate_max_tokens(max_tokens)
    except ValueError as e:
        logger.error(f"Invalid max_tokens value: {e}")
        sys.exit(ExitCode.INVALID_ARGUMENTS.value)
    
    # Get file paths
    user_prompt_file = args['prompt_file']
    system_instruction_file = args['instruction_file']
    binary_file_path = args['binary_file']
    
    # Validate required files exist
    try:
        validate_file_exists(user_prompt_file, "User prompt file")
        if system_instruction_file:
            validate_file_exists(system_instruction_file, "System instruction file")
        if binary_file_path:
            validate_file_exists(binary_file_path, "Binary file")
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(ExitCode.FILE_NOT_FOUND.value)
    
    # Read user prompt from file
    try:
        with open(user_prompt_file, 'r', encoding=FILE_ENCODING) as f:
            user_prompt_text = f.read()
    except IOError as e:
        logger.error(f"Error reading user prompt file: {e}")
        sys.exit(ExitCode.FILE_NOT_FOUND.value)
    
    # Read system instruction from file (if provided)
    system_instruction_text = None
    if system_instruction_file:
        try:
            with open(system_instruction_file, 'r', encoding=FILE_ENCODING) as f:
                system_instruction_text = f.read()
        except IOError as e:
            logger.error(f"Error reading system instruction file: {e}")
            sys.exit(ExitCode.FILE_NOT_FOUND.value)
    
    # Read and process binary file if provided
    inline_data = None
    if binary_file_path:
        mime_type, _ = mimetypes.guess_type(binary_file_path)
        if not mime_type:
            mime_type = MIME_TYPE_OCTET_STREAM
        
        try:
            with open(binary_file_path, 'rb') as f:
                binary_content = f.read()
                encoded_data = base64.b64encode(binary_content).decode('utf-8')
        except IOError as e:
            logger.error(f"Error reading binary file: {e}")
            sys.exit(ExitCode.FILE_NOT_FOUND.value)
        
        inline_data = {
            "mime_type": mime_type,
            "data": encoded_data,
            "filename": Path(binary_file_path).name,
            "path": binary_file_path,
        }
    
    # Select the appropriate API key file
    if ai_provider == AIProvider.OPENAI:
        api_key_file = OPENAI_API_KEY_FILE
    elif ai_provider == AIProvider.GEMINI:
        api_key_file = GEMINI_API_KEY_FILE
    else:  # AIProvider.CLAUDE
        api_key_file = CLAUDE_API_KEY_FILE
    
    # Read the API key from the file
    try:
        validate_file_exists(api_key_file, f"API key file")
        with open(api_key_file, 'r', encoding=FILE_ENCODING) as f:
            API_KEY = f.read().strip()
    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(ExitCode.AUTHENTICATION_ERROR.value)
    except IOError as e:
        logger.error(f"Error reading API key file: {e}")
        sys.exit(ExitCode.AUTHENTICATION_ERROR.value)
    
    result = None
    
    # OPENAI FLOW
    if ai_provider == AIProvider.OPENAI:
        uploaded_file_id = None
        try:
            if inline_data and inline_data.get("mime_type") == MIME_TYPE_PDF:
                file_id = upload_file_openai(API_KEY, inline_data["path"])
                inline_data["file_id"] = file_id
                uploaded_file_id = file_id
            
            result = call_openai_api(
                api_key=API_KEY,
                user_prompt=user_prompt_text,
                max_tokens=max_tokens,
                system_instruction=system_instruction_text,
                file_data=inline_data,
                temperature=OPENAI_TEMPERATURE,
                top_p=OPENAI_TOP_P,
                n=OPENAI_N,
                model=OPENAI_MODEL
            )
        except requests.HTTPError as e:
            logger.error(f"API request failed: {e}")
            sys.exit(ExitCode.API_ERROR.value)
        finally:
            if uploaded_file_id and OPENAI_DELETE_FILES_AFTER_USE:
                if delete_file_openai(API_KEY, uploaded_file_id):
                    logger.info(f"Privacy: Deleted uploaded file {uploaded_file_id} from OpenAI")
        
        # Extract and display the response text
        response_text = None
        if "output_text" in result:
            response_text = result["output_text"]
        elif "output" in result and result["output"]:
            texts = []
            for item in result["output"]:
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        texts.append(c.get("text", ""))
            response_text = "\n".join(t for t in texts if t)
        
        if response_text:
            print("\n=== Response ===")
            print(response_text)
            print("\n=== Full API Response ===")
    
    # GEMINI FLOW
    elif ai_provider == AIProvider.GEMINI:
        # Prepare system instruction for Gemini (only if provided)
        gemini_system_instruction = None
        if system_instruction_text:
            gemini_system_instruction = {"parts": [{"text": system_instruction_text}]}
        
        try:
            result = call_gemini_api(
                api_key=API_KEY,
                gemini_user_prompt=user_prompt_text,
                gemini_max_tokens=max_tokens,
                gemini_system_instruction=gemini_system_instruction,
                gemini_inline_data=inline_data,
                gemini_temperature=GEMINI_TEMPERATURE,
                gemini_top_p=GEMINI_TOP_P,
                gemini_top_k=GEMINI_TOP_K,
                gemini_candidate_count=GEMINI_CANDIDATE_COUNT,
                gemini_safety_threshold=GEMINI_SAFETY_THRESHOLD,
                gemini_api_version=GEMINI_API_VERSION,
                model=GEMINI_MODEL
            )
        except requests.HTTPError as e:
            logger.error(f"API request failed: {e}")
            sys.exit(ExitCode.API_ERROR.value)
        
        # Check for binary outputs
        if "candidates" in result:
            for idx, candidate in enumerate(result["candidates"]):
                if "content" in candidate and "parts" in candidate["content"]:
                    for part_idx, part in enumerate(candidate["content"]["parts"]):
                        if "inline_data" in part:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                            mime_type = part["inline_data"].get("mime_type", MIME_TYPE_OCTET_STREAM)
                            extension = mimetypes.guess_extension(mime_type) or ".bin"
                            filename = f"output_{timestamp}_c{idx}_p{part_idx}{extension}"
                            
                            binary_data = base64.b64decode(part["inline_data"]["data"])
                            with open(filename, 'wb') as f:
                                f.write(binary_data)
                            logger.info(f"Binary output written to: {filename}")
    
    # CLAUDE FLOW
    else:  # AIProvider.CLAUDE
        try:
            result = call_claude_api(
                api_key=API_KEY,
                user_prompt=user_prompt_text,
                max_tokens=max_tokens,
                system_instruction=system_instruction_text,
                inline_data=inline_data,
                temperature=CLAUDE_TEMPERATURE,
                top_p=CLAUDE_TOP_P,
                top_k=CLAUDE_TOP_K,
                model=CLAUDE_MODEL
            )
        except requests.HTTPError as e:
            logger.error(f"API request failed: {e}")
            sys.exit(ExitCode.API_ERROR.value)
    
    # Print the complete JSON response
    print(json.dumps(result, indent=2))
    
    # Print privacy information
    logger.info("\n=== Privacy Settings ===")
    if ai_provider == AIProvider.OPENAI:
        logger.info(f"OpenAI - Data retention opt-out: {not OPENAI_STORE_DATA}")
        logger.info(f"OpenAI - Auto-delete uploaded files: {OPENAI_DELETE_FILES_AFTER_USE}")
    elif ai_provider == AIProvider.GEMINI:
        logger.info(f"Gemini - Caching disabled: {not GEMINI_CACHE_CONTROL}")
    else:  # Claude
        logger.info(f"Claude - Caching disabled: {not CLAUDE_CACHE_CONTROL}")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled by user")
        sys.exit(ExitCode.SUCCESS.value)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(ExitCode.GENERAL_ERROR.value)