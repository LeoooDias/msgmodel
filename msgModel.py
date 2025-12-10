#!/usr/bin/env python3
# Shebang line allows this script to be executed directly on Unix-like systems

"""
msgModel.py
A unified LLM API script supporting OpenAI, Gemini, and Claude.

This script provides a single interface to interact with three major LLM providers:
- OpenAI (GPT models)
- Google Gemini
- Anthropic Claude

Usage: python generateResponse-unified.py <ai_family> <max_tokens> <system_instruction_file> <user_prompt_file> [binary_file]

ai_family:
    'o' for OpenAI
    'g' for Gemini/Google
    'c' for Claude/Anthropic

Example:
    python generateResponse-unified.py g 150 persona1.instruction request1.prompt document.pdf
"""

# ============================================================================
# IMPORTS
# ============================================================================
# requests: For making HTTP API calls to LLM providers
# json: For encoding/decoding JSON payloads
# sys: For command-line arguments and exit codes
# os: For file path operations
# base64: For encoding binary files (images, PDFs) to base64 strings
# mimetypes: For detecting file types from file extensions
# datetime: For generating timestamped filenames for binary outputs
# typing: For type hints to improve code readability and IDE support

import requests
import json
import sys
import os
import base64
import mimetypes
from datetime import datetime
from typing import Optional, Dict, Any, List


# ============================================================================
# CONFIGURATION - MUST BE SET BY USER
# ============================================================================
# This section contains critical configuration that must be properly set up
# before the script can function. Users must create API key files in the
# working directory with valid API keys from each provider they intend to use.

# API key files (must exist in working directory)
# These files should contain only the API key string, with no extra whitespace
OPENAI_API_KEY_FILE = 'openai-api.key'
GEMINI_API_KEY_FILE = 'gemini-api.key'
CLAUDE_API_KEY_FILE = 'claude-api.key'

# API URLs - Base endpoints for each LLM provider
# OpenAI uses the Responses API endpoint for generating completions
OPENAI_URL = "https://api.openai.com/v1/responses"
# OpenAI Files API endpoint is used for uploading PDF files before processing
OPENAI_FILES_URL = "https://api.openai.com/v1/files"
# Gemini base URL - the specific endpoint is constructed dynamically with API version and model
GEMINI_URL = "https://generativelanguage.googleapis.com"
# Claude base URL - the anthropic library handles endpoint construction
CLAUDE_URL = "https://api.anthropic.com"

# ============================================================================
# CONFIGURATION - CAN BE SET BY USER (defaults provided)
# ============================================================================
# These settings can be customized to change model behavior and response characteristics.
# Defaults are provided that work well for most use cases.

# Model selection - Specifies which specific model variant to use from each provider
# These should be updated if newer models become available or if different capabilities are needed
OPENAI_MODEL = "gpt-4o"  # GPT-4 Optimized - balanced performance and cost
GEMINI_MODEL = "gemini-2.5-pro"  # Latest Gemini Pro model with advanced reasoning
CLAUDE_MODEL = "claude-sonnet-4-20250514"  # Claude Sonnet 4 - balanced speed and intelligence

# OpenAI specific settings
OPENAI_TEMPERATURE = 1.0 # temperature: Controls randomness (0.0 = deterministic, 2.0 = very creative)
OPENAI_TOP_P = 1.0 # top_p: Nucleus sampling - considers tokens with top_p probability mass (0.0-1.0)
OPENAI_N = 1 # n: Number of completions to generate (we use 1 for single response)

# Gemini specific settings
GEMINI_TEMPERATURE = 1.0  # Same temperature concept as OpenAI
GEMINI_TOP_P = 0.95  # Slightly more focused than temperature=1.0
GEMINI_TOP_K = 40 # top_k: Considers only the top k tokens for sampling (higher = more diversity)
GEMINI_CANDIDATE_COUNT = 1 # candidate_count: Number of response variations to generate
# safety_threshold: Content filtering level (BLOCK_NONE, BLOCK_ONLY_HIGH, BLOCK_MEDIUM_AND_ABOVE, BLOCK_LOW_AND_ABOVE)
GEMINI_SAFETY_THRESHOLD = "BLOCK_NONE"
# API version: Gemini API version to use (v1beta has latest features)
GEMINI_API_VERSION = "v1beta"

# Claude specific settings
CLAUDE_TEMPERATURE = 1.0  # Same temperature concept as other models
CLAUDE_TOP_P = 0.95  # Nucleus sampling parameter
CLAUDE_TOP_K = 40  # Top-k sampling parameter


# ============================================================================
# OpenAI Functions
# ============================================================================
# Functions specific to interacting with OpenAI's API
# OpenAI requires PDF files to be uploaded separately before they can be referenced
# in API calls, unlike images which can be sent as base64-encoded data directly.

def upload_file_openai(api_key: str, file_path: str, purpose: str = "assistants") -> str:
    """
    Upload a file to OpenAI Files API and return file_id.
    
    This function is necessary for PDF files, which must be uploaded to OpenAI's
    file storage before they can be referenced in API requests.
    
    Args:
        api_key: OpenAI API authentication key
        file_path: Path to the file to upload
        purpose: Purpose of the upload ("assistants" is used for file analysis)
    
    Returns:
        str: The file_id assigned by OpenAI, used to reference the file in API calls
    
    Raises:
        requests.HTTPError: If the upload fails
    """
    url = OPENAI_FILES_URL
    # Set up authorization header with Bearer token
    headers = {"Authorization": f"Bearer {api_key}"}
    
    # Open file in binary read mode and upload it
    with open(file_path, "rb") as f:
        # Prepare multipart form data with file and purpose
        files = {"file": (os.path.basename(file_path), f)}
        data = {"purpose": purpose}
        resp = requests.post(url, headers=headers, files=files, data=data)
    
    # Check if upload was successful
    if not resp.ok:
        print(f"File upload failed {resp.status_code}: {resp.text}")
        resp.raise_for_status()  # Raise an exception for bad status codes
    
    # Extract and return the file ID from the response
    payload = resp.json()
    return payload.get("id")


def call_openai_api(
    api_key: str,
    user_prompt: str,
    max_tokens: int,
    system_instruction: Optional[str] = None,
    file_data: Optional[Dict[str, str]] = None,
    temperature: float = OPENAI_TEMPERATURE,
    top_p: float = OPENAI_TOP_P,
    n: int = OPENAI_N,
    model: str = OPENAI_MODEL
) -> Dict[str, Any]:
    """
    Make an API call to OpenAI using the Responses API, with optional file input.
    
    OpenAI's API accepts different types of content in the user message:
    - Text prompts
    - Images (as base64 data URLs)
    - PDF files (via pre-uploaded file_id)
    - Other text files (decoded and included as text)
    
    Args:
        api_key: OpenAI API key for authentication
        user_prompt: The main text prompt from the user
        max_tokens: Maximum number of tokens to generate in the response
        system_instruction: Optional system-level instructions to guide model behavior
        file_data: Optional dictionary containing file information (mime_type, data, filename, file_id)
        temperature: Controls randomness in the output
        top_p: Nucleus sampling parameter
        n: Number of completions to generate
        model: Model identifier to use
    
    Returns:
        Dict containing the API response with generated content and metadata
    """
    url = OPENAI_URL
    # Build the content array - OpenAI accepts multiple content blocks in a message
    content: List[Dict[str, Any]] = []

    # Process file_data if provided - different handling based on MIME type
    if file_data:
        mime_type = file_data["mime_type"]
        encoded_data = file_data.get("data", "")
        filename = file_data.get("filename", "input.bin")
        file_id = file_data.get("file_id")  # Only set for PDFs after upload

        # Handle images - send as base64-encoded data URLs
        if mime_type.startswith("image/"):
            content.append({
                "type": "input_image",
                "image_url": f"data:{mime_type};base64,{encoded_data}"
            })
        
        # Handle PDFs - reference the pre-uploaded file by ID
        elif mime_type == "application/pdf":
            if not file_id:
                raise ValueError("PDF provided without uploaded file_id")
            content.append({
                "type": "input_file",
                "file_id": file_id,  # Reference the uploaded file
            })
        
        # Handle text files - decode and include content directly in the prompt
        elif mime_type.startswith("text/"):
            try:
                # Decode base64 back to text
                decoded_text = base64.b64decode(encoded_data).decode("utf-8", errors="ignore")
            except Exception:
                decoded_text = ""
            if decoded_text.strip():
                content.append({
                    "type": "input_text",
                    "text": f"(Contents of {filename}):\n\n{decoded_text}"
                })
        
        # Handle unsupported file types - add a note about the file
        else:
            content.append({
                "type": "input_text",
                "text": (
                    f"[Note: A file named '{filename}' with MIME type '{mime_type}' "
                    f"was provided. You may not be able to read it directly, but you "
                    f"can still respond based on the description and prompt.]"
                )
            })

    # Always append the user's text prompt last
    content.append({
        "type": "input_text",
        "text": user_prompt
    })

    # Construct the input array with user role and all content blocks
    # OpenAI expects messages in a specific format with role and content
    input_items: List[Dict[str, Any]] = [
        {
            "role": "user",
            "content": content  # Can contain multiple content blocks (text, images, files)
        }
    ]

    # Build the main API request payload
    payload: Dict[str, Any] = {
        "model": model,  # Which model to use (e.g., gpt-4o)
        "input": input_items,  # The user message(s)
        "max_output_tokens": max_tokens,  # Limit on response length
        "temperature": temperature,  # Control randomness
        "top_p": top_p,  # Nucleus sampling parameter
    }

    # Add system instructions if provided - this guides the model's overall behavior
    if system_instruction:
        payload["instructions"] = system_instruction

    # Set up HTTP headers for the request
    headers = {
        "Content-Type": "application/json",  # Tell server we're sending JSON
        "Authorization": f"Bearer {api_key}"  # Authentication token
    }

    # Make the POST request to OpenAI API
    response = requests.post(url, headers=headers, data=json.dumps(payload))

    # Check for errors and raise exception if request failed
    if not response.ok:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()

    # Return the JSON response from the API
    return response.json()


# ============================================================================
# Gemini Functions
# ============================================================================
# Functions specific to interacting with Google's Gemini API
# Gemini has a different API structure than OpenAI, with different parameter names
# and a different way of handling file inputs. It also includes safety settings
# for content filtering.

def call_gemini_api(
    api_key: str,
    gemini_user_prompt: str,
    gemini_max_tokens: int,
    gemini_system_instruction: Optional[Dict[str, Any]] = None,
    gemini_inline_data: Optional[Dict[str, str]] = None,
    gemini_temperature: float = GEMINI_TEMPERATURE,
    gemini_top_p: float = GEMINI_TOP_P,
    gemini_top_k: int = GEMINI_TOP_K,
    gemini_candidate_count: int = GEMINI_CANDIDATE_COUNT,
    gemini_safety_threshold: str = GEMINI_SAFETY_THRESHOLD,
    gemini_api_version: str = GEMINI_API_VERSION,
    model: str = GEMINI_MODEL
) -> Dict[str, Any]:
    """
    Make an API call to Google Gemini.
    
    Gemini's API uses a different structure than OpenAI:
    - API key is passed as a URL parameter, not in headers
    - Content is organized into "parts" within "contents"
    - Inline data (files) can be embedded directly in the request
    - System instructions are a separate top-level field
    - Safety settings must be configured for content filtering
    
    Args:
        api_key: Google API key for Gemini
        gemini_user_prompt: The user's text prompt
        gemini_max_tokens: Maximum tokens to generate
        gemini_system_instruction: Optional system instruction as a dict with 'parts'
        gemini_inline_data: Optional file data dict with mime_type and base64 data
        gemini_temperature: Sampling temperature
        gemini_top_p: Nucleus sampling parameter
        gemini_top_k: Top-k sampling parameter
        gemini_candidate_count: Number of response candidates to generate
        gemini_safety_threshold: Content safety filtering level
        gemini_api_version: API version (v1beta for latest features)
        model: Model identifier
    
    Returns:
        Dict containing the API response with candidates and safety ratings
    """
    # Construct the full URL with API version, model, and API key as query parameter
    # Gemini uses API key in URL instead of Authorization header
    url = f"{GEMINI_URL}/{gemini_api_version}/models/{model}:generateContent?key={api_key}"
    
    # Build the "parts" array - Gemini organizes content into parts
    # Start with the text prompt
    parts: List[Dict[str, Any]] = [{"text": gemini_user_prompt}]
    
    # Add inline data (file) if provided
    if gemini_inline_data:
        # Gemini API only accepts mime_type and data fields in inline_data
        # Filter out any extra fields like filename or path
        filtered_inline_data = {
            "mime_type": gemini_inline_data["mime_type"],
            "data": gemini_inline_data["data"]  # Base64-encoded file content
        }
        parts.append({"inline_data": filtered_inline_data})
    
    # Build the main API request payload
    payload = {
        # Contents array contains the conversation - we send one user message with multiple parts
        "contents": [
            {
                "parts": parts  # Array of text and/or inline_data parts
            }
        ],
        # Generation configuration controls the model's output behavior
        "generationConfig": {
            "maxOutputTokens": gemini_max_tokens,
            "temperature": gemini_temperature,
            "topP": gemini_top_p,
            "topK": gemini_top_k,
            "candidateCount": gemini_candidate_count  # Number of variations to generate
        },
        # Safety settings control content filtering across multiple categories
        # Each category can be set to different threshold levels
        "safetySettings": [
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": gemini_safety_threshold},
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": gemini_safety_threshold},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": gemini_safety_threshold},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": gemini_safety_threshold}
        ]
    }
    
    # Add system instruction if provided - guides overall model behavior
    # System instruction is a top-level field in Gemini, not part of contents
    if gemini_system_instruction:
        payload["systemInstruction"] = gemini_system_instruction
    
    # Set up headers - only Content-Type needed since API key is in URL
    headers = {
        "Content-Type": "application/json"
    }
    
    # Make the POST request to Gemini API
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    # Check for errors and raise exception if request failed
    if not response.ok:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()
    
    # Return the JSON response - Gemini returns candidates array with generated content
    return response.json()


# ============================================================================
# Claude Functions
# ============================================================================
# Functions specific to interacting with Anthropic's Claude API
# Claude uses the official anthropic Python library rather than direct HTTP requests.
# It has excellent support for images and PDFs through a content blocks structure.

def call_claude_api(
    api_key: str,
    user_prompt: str,
    max_tokens: int,
    system_instruction: Optional[str] = None,
    inline_data: Optional[Dict[str, str]] = None,
    temperature: float = CLAUDE_TEMPERATURE,
    top_p: float = CLAUDE_TOP_P,
    top_k: int = CLAUDE_TOP_K,
    model: str = CLAUDE_MODEL
) -> Dict[str, Any]:
    """
    Make an API call to Anthropic Claude.
    
    Claude uses the official anthropic Python library, which provides a cleaner
    interface than raw HTTP requests. Key differences from other providers:
    - Uses the anthropic library's client.messages.create() method
    - Supports both "image" and "document" content blocks
    - System instruction is a separate parameter, not part of messages
    - Returns a structured response object that we convert to dict
    
    Args:
        api_key: Anthropic API key
        user_prompt: The user's text prompt
        max_tokens: Maximum tokens to generate
        system_instruction: Optional system-level instruction string
        inline_data: Optional file data dict with mime_type and base64 data
        temperature: Sampling temperature
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        model: Model identifier (e.g., claude-sonnet-4-20250514)
    
    Returns:
        Dict containing the API response with content blocks and usage metadata
    
    Raises:
        SystemExit: If the anthropic library is not installed
    """
    # Check if anthropic library is installed - it's required for Claude API
    try:
        from anthropic import Anthropic
    except ImportError:
        print("Error: anthropic package not installed. Install with: pip install anthropic")
        sys.exit(1)
    
    # Initialize the Anthropic client with the API key
    client = Anthropic(api_key=api_key)
    
    # Build content blocks array - Claude uses a blocks-based content structure
    content: List[Dict[str, Any]] = []
    
    # Process file data if provided
    if inline_data:
        mime_type = inline_data["mime_type"]
        data = inline_data["data"]  # Base64-encoded file content
        
        # Handle images - Claude has native image understanding
        if mime_type.startswith("image/"):
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",  # Image is provided as base64 string
                    "media_type": mime_type,
                    "data": data
                }
            })
        # Handle PDFs - Claude has excellent PDF understanding with document type
        elif mime_type == "application/pdf":
            content.append({
                "type": "document",  # Special document type for PDFs
                "source": {
                    "type": "base64",
                    "media_type": mime_type,
                    "data": data
                }
            })
    
    # Always append the user's text prompt to content blocks
    content.append({
        "type": "text",
        "text": user_prompt
    })
    
    # Construct the messages array - Claude expects an array of message objects
    # Each message has a role (user/assistant) and content (array of blocks)
    messages = [
        {
            "role": "user",
            "content": content  # Can contain text, image, and document blocks
        }
    ]
    
    # Build keyword arguments for the API call
    kwargs = {
        "model": model,
        "max_tokens": max_tokens,  # Required parameter for Claude
        "messages": messages,
        "temperature": temperature,
        "top_p": top_p,
        "top_k": top_k
    }
    
    # Add system instruction if provided - separate from messages
    if system_instruction:
        kwargs["system"] = system_instruction
    
    # Make the API call using the anthropic library
    # This returns a Message object which we'll convert to a dict
    response = client.messages.create(**kwargs)
    
    # Convert the response object to a dictionary for consistency with other providers
    # Extract key fields from the structured response
    return {
        "id": response.id,  # Unique ID for this response
        "model": response.model,  # Model that generated the response
        "role": response.role,  # Should be "assistant"
        "content": [  # Array of content blocks in the response
            {
                "type": block.type,
                "text": block.text if hasattr(block, 'text') else None
            } for block in response.content
        ],
        "stop_reason": response.stop_reason,  # Why generation stopped (e.g., "end_turn")
        "usage": {  # Token usage information
            "input_tokens": response.usage.input_tokens,
            "output_tokens": response.usage.output_tokens
        }
    }


# ============================================================================
# Main Execution
# ============================================================================
# The main function orchestrates the entire flow:
# 1. Parse command-line arguments
# 2. Read system instructions and user prompt from files
# 3. Optionally read and encode a binary file (image, PDF, etc.)
# 4. Select and call the appropriate AI provider's API
# 5. Process and display the response

def main():
    """Main entry point for the script."""
    
    # Check if minimum required arguments are provided
    if len(sys.argv) < 5:
        print("Usage: python generateResponse-unified.py <ai_family> <max_tokens> <system_instruction_file> <user_prompt_file> [binary_file]")
        print("  ai_family: 'o' for OpenAI, 'g' for Gemini/Google, 'c' for Claude/Anthropic")
        sys.exit(1)
    
    # Parse command-line arguments
    # sys.argv[0] is the script name, so arguments start at index 1
    ai_family = sys.argv[1].lower()  # Which AI provider to use
    max_tokens = int(sys.argv[2])  # Maximum response length
    system_instruction_file = sys.argv[3]  # File containing system-level instructions
    user_prompt_file = sys.argv[4]  # File containing the user's prompt
    
    # Validate that the AI family is one of the supported options
    if ai_family not in ['o', 'g', 'c']:
        print(f"Error: Invalid AI family '{ai_family}'. Use 'o' (OpenAI), 'g' (Gemini), or 'c' (Claude)")
        sys.exit(1)
    
    # Read system instruction from file
    # System instructions guide the AI's overall behavior and persona
    with open(system_instruction_file, 'r') as f:
        system_instruction_text = f.read()
    
    # Read user prompt from file
    # This is the main query or task for the AI to respond to
    with open(user_prompt_file, 'r') as f:
        user_prompt_text = f.read()
    
    # Read and process binary file if provided (5th argument is optional)
    inline_data = None
    binary_file_path = None
    if len(sys.argv) >= 6:
        binary_file_path = sys.argv[5]
        
        # Detect the MIME type from the file extension
        # This tells us what kind of file it is (image/png, application/pdf, etc.)
        mime_type, _ = mimetypes.guess_type(binary_file_path)
        if not mime_type:
            # If MIME type can't be determined, use generic binary type
            mime_type = "application/octet-stream"
        
        # Read the file in binary mode and encode it to base64
        # Base64 encoding allows binary data to be transmitted as text in JSON
        with open(binary_file_path, 'rb') as f:
            binary_content = f.read()
            encoded_data = base64.b64encode(binary_content).decode('utf-8')
        
        # Store all file information in a dictionary
        inline_data = {
            "mime_type": mime_type,  # Type of file
            "data": encoded_data,  # Base64-encoded content
            "filename": os.path.basename(binary_file_path),  # Just the filename, not full path
            "path": binary_file_path,  # Full path (needed for OpenAI PDF upload)
        }
    
    # Select the appropriate API key file based on which AI provider was chosen
    # Each provider requires its own API key
    if ai_family == 'o':
        api_key_file = OPENAI_API_KEY_FILE
    elif ai_family == 'g':
        api_key_file = GEMINI_API_KEY_FILE
    else:  # ai_family == 'c'
        api_key_file = CLAUDE_API_KEY_FILE
    
    # Read the API key from the file
    # The file should contain only the API key string with no extra content
    try:
        with open(api_key_file, 'r') as f:
            API_KEY = f.read().strip()  # strip() removes any trailing whitespace/newlines
    except FileNotFoundError:
        print(f"Error: API key file '{api_key_file}' not found")
        sys.exit(1)
    
    # Initialize result variable - will hold the API response
    result = None
    
    # OPENAI FLOW
    if ai_family == 'o':
        # Special handling for PDFs with OpenAI
        # OpenAI requires PDFs to be uploaded first and referenced by file_id
        if inline_data and inline_data.get("mime_type") == "application/pdf":
            # Upload the PDF file and get a file_id back
            file_id = upload_file_openai(API_KEY, inline_data["path"])
            inline_data["file_id"] = file_id  # Store file_id for use in API call
        
        # Make the API call to OpenAI
        result = call_openai_api(
            api_key=API_KEY,
            user_prompt=user_prompt_text,
            system_instruction=system_instruction_text,
            file_data=inline_data,  # May be None if no file provided
            max_tokens=max_tokens
        )
        
        # Extract and display the response text from OpenAI's response structure
        # OpenAI's response format can vary, so we check multiple possible locations
        response_text = None
        if "output_text" in result:
            # Simpler response format
            response_text = result["output_text"]
        elif "output" in result and result["output"]:
            # More complex response format with nested structure
            texts = []
            for item in result["output"]:
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        texts.append(c.get("text", ""))
            response_text = "\n".join(t for t in texts if t)
        
        # Print extracted response text separately for easier reading
        if response_text:
            print("\n=== Response ===")
            print(response_text)
            print("\n=== Full API Response ===")
    
    # GEMINI FLOW
    elif ai_family == 'g':
        # Make the API call to Gemini
        # Note: Gemini's system instruction needs to be wrapped in a specific format
        result = call_gemini_api(
            api_key=API_KEY,
            gemini_user_prompt=user_prompt_text,
            gemini_system_instruction={"parts": [{"text": system_instruction_text}]},  # Gemini format
            gemini_inline_data=inline_data,  # May be None if no file provided
            gemini_max_tokens=max_tokens
        )
        
        # Check for binary outputs in Gemini response
        # Gemini can return binary data (e.g., generated images) in its response
        # We need to extract and save these to files
        if "candidates" in result:
            for idx, candidate in enumerate(result["candidates"]):
                if "content" in candidate and "parts" in candidate["content"]:
                    # Iterate through all parts in the response
                    for part_idx, part in enumerate(candidate["content"]["parts"]):
                        # Check if this part contains binary data
                        if "inline_data" in part:
                            # Generate a unique filename with timestamp
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                            mime_type = part["inline_data"].get("mime_type", "application/octet-stream")
                            # Determine file extension from MIME type
                            extension = mimetypes.guess_extension(mime_type) or ".bin"
                            # Create filename with candidate and part indices for uniqueness
                            filename = f"output_{timestamp}_c{idx}_p{part_idx}{extension}"
                            
                            # Decode base64 data and write to file
                            binary_data = base64.b64decode(part["inline_data"]["data"])
                            with open(filename, 'wb') as f:
                                f.write(binary_data)
                            print(f"Binary output written to: {filename}")
    
    # CLAUDE FLOW
    else:  # ai_family == 'c'
        # Make the API call to Claude
        # Claude's API is the most straightforward thanks to the anthropic library
        result = call_claude_api(
            api_key=API_KEY,
            user_prompt=user_prompt_text,
            system_instruction=system_instruction_text,
            inline_data=inline_data,  # May be None if no file provided
            max_tokens=max_tokens
        )
    
    # Print the complete JSON response from the API
    # This shows the full structure including metadata, tokens used, etc.
    # Using indent=2 makes the JSON human-readable with proper formatting
    print(json.dumps(result, indent=2))


# Standard Python idiom - only run main() if this script is executed directly
# (not if it's imported as a module in another script)
if __name__ == "__main__":
    main()
