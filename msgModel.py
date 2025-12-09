#!/usr/bin/env python3
"""
msgModel.py
A unified LLM API script supporting OpenAI, Gemini, and Claude.

Usage: python generateResponse-unified.py <ai_family> <max_tokens> <system_instruction_file> <user_prompt_file> [binary_file]

ai_family: 'o' for OpenAI, 'g' for Gemini/Google, 'c' for Claude/Anthropic
"""

import requests
import json
import sys
import os
import base64
import mimetypes
from datetime import datetime
from typing import Optional, Dict, Any, List


# ============================================================================
# OpenAI Functions
# ============================================================================

def upload_file_openai(api_key: str, file_path: str, purpose: str = "assistants") -> str:
    """Upload a file to OpenAI Files API and return file_id."""
    url = "https://api.openai.com/v1/files"
    headers = {"Authorization": f"Bearer {api_key}"}
    with open(file_path, "rb") as f:
        files = {"file": (os.path.basename(file_path), f)}
        data = {"purpose": purpose}
        resp = requests.post(url, headers=headers, files=files, data=data)
    if not resp.ok:
        print(f"File upload failed {resp.status_code}: {resp.text}")
        resp.raise_for_status()
    payload = resp.json()
    return payload.get("id")


def call_openai_api(
    api_key: str,
    user_prompt: str,
    max_tokens: int,
    system_instruction: Optional[str] = None,
    file_data: Optional[Dict[str, str]] = None,
    temperature: float = 1.0,
    top_p: float = 1.0,
    n: int = 1,
    model: str = "gpt-4o"
) -> Dict[str, Any]:
    """
    Make an API call to OpenAI using the Responses API, with optional file input.
    """
    url = "https://api.openai.com/v1/responses"
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
        elif mime_type == "application/pdf":
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

    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {api_key}"
    }

    response = requests.post(url, headers=headers, data=json.dumps(payload))

    if not response.ok:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()

    return response.json()


# ============================================================================
# Gemini Functions
# ============================================================================

def call_gemini_api(
    api_key: str,
    gemini_user_prompt: str,
    gemini_max_tokens: int,
    gemini_system_instruction: Optional[Dict[str, Any]] = None,
    gemini_inline_data: Optional[Dict[str, str]] = None,
    gemini_temperature: float = 1.0,
    gemini_top_p: float = 0.95,
    gemini_top_k: int = 40,
    gemini_candidate_count: int = 1,
    gemini_safety_threshold: str = "BLOCK_ONLY_HIGH",
    gemini_api_version: str = "v1beta",
    model: str = "gemini-2.5-pro"
) -> Dict[str, Any]:
    """
    Make an API call to Google Gemini.
    """
    url = f"https://generativelanguage.googleapis.com/{gemini_api_version}/models/{model}:generateContent?key={api_key}"
    
    parts: List[Dict[str, Any]] = [{"text": gemini_user_prompt}]
    if gemini_inline_data:
        # Gemini API only accepts mime_type and data fields
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
        "Content-Type": "application/json"
    }
    
    response = requests.post(url, headers=headers, data=json.dumps(payload))
    
    if not response.ok:
        print(f"Error {response.status_code}: {response.text}")
        response.raise_for_status()
    
    return response.json()


# ============================================================================
# Claude Functions
# ============================================================================

def call_claude_api(
    api_key: str,
    user_prompt: str,
    max_tokens: int,
    system_instruction: Optional[str] = None,
    inline_data: Optional[Dict[str, str]] = None,
    temperature: float = 1.0,
    top_p: float = 0.95,
    top_k: int = 40,
    model: str = "claude-sonnet-4-20250514"
) -> Dict[str, Any]:
    """
    Make an API call to Anthropic Claude.
    """
    try:
        from anthropic import Anthropic
    except ImportError:
        print("Error: anthropic package not installed. Install with: pip install anthropic")
        sys.exit(1)
    
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
        elif mime_type == "application/pdf":
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

def main():
    if len(sys.argv) < 5:
        print("Usage: python generateResponse-unified.py <ai_family> <max_tokens> <system_instruction_file> <user_prompt_file> [binary_file]")
        print("  ai_family: 'o' for OpenAI, 'g' for Gemini/Google, 'c' for Claude/Anthropic")
        sys.exit(1)
    
    # Parse arguments
    ai_family = sys.argv[1].lower()
    max_tokens = int(sys.argv[2])
    system_instruction_file = sys.argv[3]
    user_prompt_file = sys.argv[4]
    
    # Validate AI family
    if ai_family not in ['o', 'g', 'c']:
        print(f"Error: Invalid AI family '{ai_family}'. Use 'o' (OpenAI), 'g' (Gemini), or 'c' (Claude)")
        sys.exit(1)
    
    # Read system instruction
    with open(system_instruction_file, 'r') as f:
        system_instruction_text = f.read()
    
    # Read user prompt
    with open(user_prompt_file, 'r') as f:
        user_prompt_text = f.read()
    
    # Read binary file if provided
    inline_data = None
    binary_file_path = None
    if len(sys.argv) >= 6:
        binary_file_path = sys.argv[5]
        mime_type, _ = mimetypes.guess_type(binary_file_path)
        if not mime_type:
            mime_type = "application/octet-stream"
        
        with open(binary_file_path, 'rb') as f:
            binary_content = f.read()
            encoded_data = base64.b64encode(binary_content).decode('utf-8')
        
        inline_data = {
            "mime_type": mime_type,
            "data": encoded_data,
            "filename": os.path.basename(binary_file_path),
            "path": binary_file_path,
        }
    
    # Read appropriate API key based on AI family
    if ai_family == 'o':
        api_key_file = 'openai-api.key'
    elif ai_family == 'g':
        api_key_file = 'gemini-api.key'
    else:  # ai_family == 'c'
        api_key_file = 'claude-api.key'
    
    try:
        with open(api_key_file, 'r') as f:
            API_KEY = f.read().strip()
    except FileNotFoundError:
        print(f"Error: API key file '{api_key_file}' not found")
        sys.exit(1)
    
    # Call the appropriate API
    result = None
    
    if ai_family == 'o':
        # OpenAI
        if inline_data and inline_data.get("mime_type") == "application/pdf":
            file_id = upload_file_openai(API_KEY, inline_data["path"])
            inline_data["file_id"] = file_id
        
        result = call_openai_api(
            api_key=API_KEY,
            user_prompt=user_prompt_text,
            system_instruction=system_instruction_text,
            file_data=inline_data,
            max_tokens=max_tokens
        )
        
        # Extract response text for OpenAI
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
    
    elif ai_family == 'g':
        # Gemini
        result = call_gemini_api(
            api_key=API_KEY,
            gemini_user_prompt=user_prompt_text,
            gemini_system_instruction={"parts": [{"text": system_instruction_text}]},
            gemini_inline_data=inline_data,
            gemini_max_tokens=max_tokens
        )
        
        # Check for binary outputs in Gemini response
        if "candidates" in result:
            for idx, candidate in enumerate(result["candidates"]):
                if "content" in candidate and "parts" in candidate["content"]:
                    for part_idx, part in enumerate(candidate["content"]["parts"]):
                        if "inline_data" in part:
                            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                            mime_type = part["inline_data"].get("mime_type", "application/octet-stream")
                            extension = mimetypes.guess_extension(mime_type) or ".bin"
                            filename = f"output_{timestamp}_c{idx}_p{part_idx}{extension}"
                            
                            binary_data = base64.b64decode(part["inline_data"]["data"])
                            with open(filename, 'wb') as f:
                                f.write(binary_data)
                            print(f"Binary output written to: {filename}")
    
    else:  # ai_family == 'c'
        # Claude
        result = call_claude_api(
            api_key=API_KEY,
            user_prompt=user_prompt_text,
            system_instruction=system_instruction_text,
            inline_data=inline_data,
            max_tokens=max_tokens
        )
    
    # Print the result
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
