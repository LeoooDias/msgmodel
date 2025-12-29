"""
msgmodel.providers.openai
~~~~~~~~~~~~~~~~~~~~~~~~~

OpenAI API provider implementation.

DATA HANDLING:
- OpenAI does not use API data for model training (standard policy since March 2023).
- The X-OpenAI-No-Store header is sent by default to request zero data storage.
- Zero Data Retention (ZDR) requires separate eligibility from OpenAI.
- See: https://platform.openai.com/docs/models/how-we-use-your-data

FILE UPLOADS:
- All file uploads are via inline base64-encoding in prompts (no Files API)
- Files are limited to practical API size constraints (~15-20MB)
- Provides stateless operation
"""

import json
import base64
import logging
from typing import Optional, Dict, Any, Iterator, List, Callable

import requests

from ..config import OpenAIConfig, OPENAI_URL
from ..exceptions import APIError, ProviderError, StreamingError

logger = logging.getLogger(__name__)

# MIME type constants
MIME_TYPE_JSON = "application/json"


class OpenAIProvider:
    """
    OpenAI API provider for making LLM requests.
    
    Handles API calls and response parsing for OpenAI models.
    All file uploads use inline base64-encoding for stateless operation.
    """
    
    def __init__(self, api_key: str, config: Optional[OpenAIConfig] = None):
        """
        Initialize the OpenAI provider.
        
        Args:
            api_key: OpenAI API key
            config: Optional configuration (uses defaults if not provided)
        """
        self.api_key = api_key
        self.config = config or OpenAIConfig()
    
    def _build_headers(self) -> Dict[str, str]:
        """
        Build HTTP headers for OpenAI API requests.
        
        Includes the X-OpenAI-No-Store header by default to request zero data storage.
        Note: Training opt-out is automatic; ZDR (zero storage) requires eligibility.
        
        Returns:
            Dictionary of HTTP headers
        """
        headers: Dict[str, str] = {
            "Content-Type": MIME_TYPE_JSON,
            "Authorization": f"Bearer {self.api_key}",
            "X-OpenAI-No-Store": "true"  # Request zero storage (ZDR eligibility required)
        }
        
        return headers
    
    def _build_content(
        self,
        prompt: str,
        file_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Build the content array for the API request."""
        content: List[Dict[str, Any]] = []
        
        if file_data:
            mime_type = file_data["mime_type"]
            encoded_data = file_data.get("data", "")
            filename = file_data.get("filename", "input.bin")
            
            if mime_type.startswith("image/"):
                content.append({
                    "type": "image_url",
                    "image_url": {
                        "url": f"data:{mime_type};base64,{encoded_data}"
                    }
                })
            elif mime_type.startswith("text/"):
                try:
                    decoded_text = base64.b64decode(encoded_data).decode("utf-8", errors="ignore")
                except Exception:
                    decoded_text = ""
                if decoded_text.strip():
                    content.append({
                        "type": "text",
                        "text": f"(Contents of {filename}):\n\n{decoded_text}"
                    })
            else:
                content.append({
                    "type": "text",
                    "text": (
                        f"[Note: A file named '{filename}' with MIME type '{mime_type}' "
                        f"was provided. You may not be able to read it directly, but you "
                        f"can still respond based on the description and prompt.]"
                    )
                })
        
        content.append({
            "type": "text",
            "text": prompt
        })
        
        return content
    
    def _supports_max_completion_tokens(self, model_name: str) -> bool:
        """
        Check if model supports max_completion_tokens (modern OpenAI standard).
        
        v3.2.1 Enhancement: Prefer max_completion_tokens for all models except known legacy ones.
        This ensures compatibility with GPT-5, GPT-6, and future models automatically.
        
        Args:
            model_name: The model identifier
            
        Returns:
            True if model uses max_completion_tokens (default for new models),
            False only for known legacy models that require max_tokens
        """
        # Models that ONLY support max_tokens (legacy, pre-GPT-4o era)
        # Check these first before checking prefixes
        legacy_exact_matches = [
            "gpt-3.5-turbo",
            "gpt-4",
        ]
        
        # If exact match to legacy model, use max_tokens
        if model_name in legacy_exact_matches:
            return False
        
        # Check for legacy models with version suffixes
        # gpt-3.5-turbo-0613, gpt-4-0613, etc.
        legacy_prefixes_with_version = [
            "gpt-3.5-turbo-",
            "gpt-4-0",  # gpt-4-0613, gpt-4-0125-preview, etc. (but NOT gpt-4-turbo)
        ]
        
        for legacy_prefix in legacy_prefixes_with_version:
            if model_name.startswith(legacy_prefix):
                # Make sure gpt-4-turbo is not caught by "gpt-4-0" check
                if legacy_prefix == "gpt-4-0" and "turbo" in model_name:
                    continue
                return False
        
        # All other models use max_completion_tokens:
        # - GPT-4o (all versions): gpt-4o, gpt-4o-mini, gpt-4o-2024-*
        # - GPT-4-turbo (all versions): gpt-4-turbo, gpt-4-turbo-preview
        # - GPT-5 and future models
        # This future-proofs the implementation
        return True
    
    def _build_payload(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Build the API request payload for OpenAI Chat Completions API."""
        content = self._build_content(prompt, file_data)
        
        # Build messages array with system message first (if provided)
        messages: List[Dict[str, Any]] = []
        if system_instruction:
            messages.append({"role": "system", "content": system_instruction})
        messages.append({"role": "user", "content": content})
        
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "messages": messages,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }
        
        # Use appropriate max tokens parameter based on model version
        # v3.2.1: Support both max_tokens (legacy) and max_completion_tokens (GPT-4o+)
        if self._supports_max_completion_tokens(self.config.model):
            payload["max_completion_tokens"] = self.config.max_tokens
        else:
            payload["max_tokens"] = self.config.max_tokens
        
        if stream:
            payload["stream"] = True
        
        return payload
    
    def query(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a non-streaming API call to OpenAI.
        
        The X-OpenAI-No-Store header is sent by default, opting out of data
        retention for model training.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            file_data: Optional file data dict
            
        Returns:
            The API response as a dictionary
            
        Raises:
            APIError: If the API call fails
        """
        payload = self._build_payload(prompt, system_instruction, file_data)
        headers = self._build_headers()
        
        try:
            response = requests.post(
                OPENAI_URL,
                headers=headers,
                data=json.dumps(payload)
            )
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")
        
        if not response.ok:
            raise APIError(
                f"OpenAI API error: {response.text}",
                status_code=response.status_code,
                response_text=response.text
            )
        
        return response.json()
    
    def stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None,
        timeout: float = 300,
        on_chunk: Optional[Callable[[str], bool]] = None
    ) -> Iterator[str]:
        """
        Make a streaming API call to OpenAI.
        
        The X-OpenAI-No-Store header is sent by default, opting out of data
        retention for model training.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            file_data: Optional file data dict
            timeout: Timeout in seconds for the streaming connection (default: 300s/5min)
            on_chunk: Optional callback that receives each chunk. Return False to abort stream.
            
        Yields:
            Text chunks as they arrive
            
        Raises:
            APIError: If the API call fails
            StreamingError: If streaming fails or timeout occurs
        """
        payload = self._build_payload(prompt, system_instruction, file_data, stream=True)
        headers = self._build_headers()
        
        try:
            response = requests.post(
                OPENAI_URL,
                headers=headers,
                data=json.dumps(payload),
                stream=True,
                timeout=timeout
            )
        except requests.Timeout:
            raise StreamingError(f"OpenAI streaming request timed out after {timeout} seconds")
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")
        
        if not response.ok:
            raise APIError(
                f"OpenAI API error: {response.text}",
                status_code=response.status_code,
                response_text=response.text
            )
        
        chunks_received = 0
        sample_chunks = []  # For debugging error messages
        try:
            for line in response.iter_lines():
                if line:
                    line_text = line.decode("utf-8")
                    if line_text.startswith("data: "):
                        data = line_text[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            
                            # Store sample chunks for debugging (limit to first 3)
                            if len(sample_chunks) < 3:
                                sample_chunks.append(chunk)
                            
                            # Check for error in stream (e.g., rate limiting)
                            # Error structure: {"error": {"message": "...", "type": "..."}}
                            if "error" in chunk and isinstance(chunk.get("error"), dict):
                                error_obj = chunk["error"]
                                error_msg = error_obj.get("message", "Unknown error")
                                error_type = error_obj.get("type", "unknown")
                                
                                # Check if it's a rate limit error
                                if error_type == "rate_limit_error" or "rate_limit" in error_msg.lower():
                                    raise APIError(
                                        f"OpenAI rate limit exceeded during streaming: {error_msg}",
                                        status_code=429,
                                        response_text=json.dumps(chunk),
                                        provider="openai"
                                    )
                                else:
                                    raise APIError(
                                        f"OpenAI API error during streaming ({error_type}): {error_msg}",
                                        status_code=None,
                                        response_text=json.dumps(chunk),
                                        provider="openai"
                                    )
                            
                            # Extract text from OpenAI Chat Completions streaming response
                            # Format: {"choices": [{"delta": {"content": "..."}}], ...}
                            if "choices" in chunk and isinstance(chunk["choices"], list):
                                for choice in chunk["choices"]:
                                    if isinstance(choice, dict):
                                        delta = choice.get("delta", {})
                                        if isinstance(delta, dict):
                                            text = delta.get("content", "")
                                            if text:
                                                chunks_received += 1
                                                # v3.2.1: Support abort callback
                                                if on_chunk is not None:
                                                    should_continue = on_chunk(text)
                                                    if should_continue is False:
                                                        return
                                                yield text
                        except json.JSONDecodeError:
                            continue
            
            # Raise error if no chunks were received
            if chunks_received == 0:
                error_msg = (
                    "No text chunks extracted from OpenAI streaming response. "
                    "Response format may not match OpenAI Chat Completions delta structure "
                    "or stream may have ended prematurely."
                )
                if sample_chunks:
                    error_msg += f"\n\nSample chunks received (for debugging):\n"
                    for i, chunk in enumerate(sample_chunks, 1):
                        error_msg += f"  Chunk {i}: {json.dumps(chunk)}\n"
                
                raise StreamingError(error_msg, chunks_received=0)
        except StreamingError:
            # Re-raise StreamingError as-is
            raise
        except APIError:
            # Re-raise APIError as-is
            raise
        except Exception as e:
            raise StreamingError(f"Streaming interrupted: {e}", chunks_received=chunks_received)

    def stream_with_finish_reason(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None,
        timeout: float = 300,
        on_chunk: Optional[Callable[[str], bool]] = None
    ) -> Iterator[Dict[str, Any]]:
        """
        Make a streaming API call to OpenAI, yielding chunks and finish_reason.
        
        Similar to stream(), but yields dictionaries with chunk text and metadata,
        including the final finish_reason when the stream completes.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            file_data: Optional file data dict
            timeout: Timeout in seconds for the streaming connection (default: 300s/5min)
            on_chunk: Optional callback that receives each chunk. Return False to abort stream.
            
        Yields:
            Dict with keys:
            - "type": "delta" for text chunks, "finish" for completion
            - "text": The text content (for delta events)
            - "finish_reason": The finish reason (for finish events)
              Values: "stop", "length", "content_filter", "tool_calls", or None
            
        Raises:
            APIError: If the API call fails
            StreamingError: If streaming fails or timeout occurs
        """
        payload = self._build_payload(prompt, system_instruction, file_data, stream=True)
        headers = self._build_headers()
        
        try:
            response = requests.post(
                OPENAI_URL,
                headers=headers,
                data=json.dumps(payload),
                stream=True,
                timeout=timeout
            )
        except requests.Timeout:
            raise StreamingError(f"OpenAI streaming request timed out after {timeout} seconds")
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")
        
        if not response.ok:
            raise APIError(
                f"OpenAI API error: {response.text}",
                status_code=response.status_code,
                response_text=response.text
            )
        
        chunks_received = 0
        sample_chunks = []
        finish_reason = None
        
        try:
            for line in response.iter_lines():
                if line:
                    line_text = line.decode("utf-8")
                    if line_text.startswith("data: "):
                        data = line_text[6:]
                        if data == "[DONE]":
                            break
                        try:
                            chunk = json.loads(data)
                            
                            if len(sample_chunks) < 3:
                                sample_chunks.append(chunk)
                            
                            # Check for error in stream
                            if "error" in chunk and isinstance(chunk.get("error"), dict):
                                error_obj = chunk["error"]
                                error_msg = error_obj.get("message", "Unknown error")
                                error_type = error_obj.get("type", "unknown")
                                
                                if error_type == "rate_limit_error" or "rate_limit" in error_msg.lower():
                                    raise APIError(
                                        f"OpenAI rate limit exceeded during streaming: {error_msg}",
                                        status_code=429,
                                        response_text=json.dumps(chunk),
                                        provider="openai"
                                    )
                                else:
                                    raise APIError(
                                        f"OpenAI API error during streaming ({error_type}): {error_msg}",
                                        status_code=None,
                                        response_text=json.dumps(chunk),
                                        provider="openai"
                                    )
                            
                            # Extract text and finish_reason from OpenAI streaming response
                            if "choices" in chunk and isinstance(chunk["choices"], list):
                                for choice in chunk["choices"]:
                                    if isinstance(choice, dict):
                                        # Capture finish_reason when present
                                        if "finish_reason" in choice and choice["finish_reason"]:
                                            finish_reason = choice["finish_reason"]
                                        
                                        delta = choice.get("delta", {})
                                        if isinstance(delta, dict):
                                            text = delta.get("content", "")
                                            if text:
                                                chunks_received += 1
                                                if on_chunk is not None:
                                                    should_continue = on_chunk(text)
                                                    if should_continue is False:
                                                        # Yield finish with abort reason
                                                        yield {"type": "finish", "finish_reason": "aborted"}
                                                        return
                                                yield {"type": "delta", "text": text}
                        except json.JSONDecodeError:
                            continue
            
            # Yield finish event with final finish_reason
            yield {"type": "finish", "finish_reason": finish_reason}
            
            if chunks_received == 0:
                error_msg = (
                    "No text chunks extracted from OpenAI streaming response. "
                    "Response format may not match OpenAI Chat Completions delta structure "
                    "or stream may have ended prematurely."
                )
                if sample_chunks:
                    error_msg += f"\n\nSample chunks received (for debugging):\n"
                    for i, chunk in enumerate(sample_chunks, 1):
                        error_msg += f"  Chunk {i}: {json.dumps(chunk)}\n"
                
                raise StreamingError(error_msg, chunks_received=0)
        except StreamingError:
            raise
        except APIError:
            raise
        except Exception as e:
            raise StreamingError(f"Streaming interrupted: {e}", chunks_received=chunks_received)
    
    @staticmethod
    def extract_text(response: Dict[str, Any]) -> str:
        """
        Extract text from an OpenAI Chat Completions response.
        
        Args:
            response: The raw API response
            
        Returns:
            Extracted text content
        """
        # OpenAI Chat Completions response format:
        # {"choices": [{"message": {"content": "..."}}], ...}
        if "choices" in response and isinstance(response["choices"], list):
            for choice in response["choices"]:
                if isinstance(choice, dict):
                    message = choice.get("message", {})
                    if isinstance(message, dict):
                        content = message.get("content", "")
                        if content:
                            return content
        
        return ""
    
    @staticmethod
    def get_privacy_info() -> Dict[str, Any]:
        """
        Get privacy and data handling information for this provider.
        
        Returns:
            Dictionary with privacy metadata
        """
        return {
            "provider": "openai",
            "training_retention": False,
            "data_retention": "Standard API: ~30 days (ZDR eligibility required for zero storage)",
            "enforcement_level": "api_policy",
            "provider_policy": "OpenAI does not use API data for model training (standard policy). X-OpenAI-No-Store header sent for ZDR-eligible accounts.",
            "special_conditions": "Training opt-out is automatic for all API users. Zero Data Retention (no storage) requires separate eligibility from OpenAI.",
            "reference": "https://platform.openai.com/docs/models/how-we-use-your-data"
        }
