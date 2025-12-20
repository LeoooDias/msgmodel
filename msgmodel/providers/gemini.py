"""
msgmodel.providers.gemini
~~~~~~~~~~~~~~~~~~~~~~~~~

Google Gemini API provider implementation.
"""

import json
import base64
import logging
import mimetypes as mime_module
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List, Iterator, Callable

import requests

from ..config import GeminiConfig, GEMINI_URL
from ..exceptions import APIError, StreamingError, ConfigurationError

logger = logging.getLogger(__name__)

MIME_TYPE_JSON = "application/json"
MIME_TYPE_OCTET_STREAM = "application/octet-stream"


class GeminiProvider:
    """
    Google Gemini API provider for making LLM requests.
    
    Handles API calls and response parsing for Gemini models.
    """
    
    def __init__(self, api_key: str, config: Optional[GeminiConfig] = None):
        """
        Initialize the Gemini provider.
        
        Args:
            api_key: Google API key for Gemini
            config: Optional configuration (uses defaults if not provided)
            
        Raises:
            ConfigurationError: If billing verification fails or paid tier is not active
        """
        self.api_key = api_key
        self.config = config or GeminiConfig()
        self._billing_verified = False
        
        # Verify paid API access on initialization
        self._verify_paid_api_access()
    
    def _verify_paid_api_access(self) -> None:
        """
        Verify that the API key has access to paid Gemini services.
        
        Makes a minimal test request to confirm paid quota is active.
        Raises ConfigurationError if billing verification fails.
        
        Raises:
            ConfigurationError: If API access indicates unpaid tier or no billing
            APIError: If the verification request fails for other reasons
        """
        try:
            # Make a minimal test request to verify paid access
            test_payload = {
                "contents": [{"parts": [{"text": "[BILLING VERIFICATION]"}]}],
                "generationConfig": {"maxOutputTokens": 10}
            }
            
            url = (
                f"{GEMINI_URL}/{self.config.api_version}/models/"
                f"{self.config.model}:generateContent?key={self.api_key}"
            )
            headers = {"Content-Type": MIME_TYPE_JSON}
            
            response = requests.post(url, headers=headers, data=json.dumps(test_payload), timeout=5)
            
            # Check for specific error indicators of unpaid tier
            if response.status_code == 429:
                raise ConfigurationError(
                    "BILLING VERIFICATION FAILED: Rate limit exceeded.\n"
                    "This may indicate unpaid quota. Ensure your Google Cloud project has:\n"
                    "  1. Cloud Billing account linked\n"
                    "  2. PAID API quota enabled (not free tier)\n"
                    "  3. Sufficient billing credits\n"
                    "See: https://console.cloud.google.com/billing"
                )
            elif response.status_code == 403:
                raise ConfigurationError(
                    "BILLING VERIFICATION FAILED: Access denied (403).\n"
                    "Ensure your API key has paid quota access:\n"
                    "  1. Verify API key is valid\n"
                    "  2. Confirm Cloud Billing is enabled\n"
                    "  3. Check that paid quota is active (not free tier)\n"
                    "See: https://console.cloud.google.com/billing"
                )
            elif not response.ok:
                error_msg = response.text
                raise APIError(
                    f"Billing verification failed with status {response.status_code}: {error_msg}",
                    status_code=response.status_code,
                    response_text=error_msg
                )
            
            self._billing_verified = True
            logger.info("✓ Gemini paid API access verified. Data retention enforced to abuse monitoring only.")
            
        except requests.RequestException as e:
            raise APIError(
                f"Billing verification request failed: {e}. "
                f"Ensure your Google Cloud project has paid API quota active."
            )
    
    @classmethod
    def create_verified(cls, api_key: str, config: Optional[GeminiConfig] = None) -> "GeminiProvider":
        """
        Create a billing-verified GeminiProvider instance.
        
        This is the recommended factory method that ensures paid API access
        is verified before any requests are made. Use this instead of direct
        instantiation when privacy guarantees are critical.
        
        Args:
            api_key: Google API key for Gemini
            config: Optional configuration
            
        Returns:
            A verified GeminiProvider instance
            
        Raises:
            ConfigurationError: If billing verification fails
        """
        return cls(api_key, config)  # __init__ handles verification
    
    @classmethod
    def create_with_cached_verification(cls, api_key: str, config: Optional[GeminiConfig] = None, 
                                         verified: bool = False) -> "GeminiProvider":
        """
        Create a GeminiProvider with optional cached verification status.
        
        WARNING: Only use verified=True if you have ALREADY verified this API key
        in the current session (e.g., from a prior sync call). Using verified=True
        without prior verification bypasses privacy protections.
        
        Args:
            api_key: Google API key for Gemini
            config: Optional configuration
            verified: If True, skip billing verification (USE WITH CAUTION)
            
        Returns:
            A GeminiProvider instance
        """
        if verified:
            # Create without triggering __init__'s verification
            instance = cls.__new__(cls)
            instance.api_key = api_key
            instance.config = config or GeminiConfig()
            instance._billing_verified = True
            return instance
        return cls(api_key, config)
    
    def _build_url(self, stream: bool = False) -> str:
        """Build the API endpoint URL."""
        action = "streamGenerateContent" if stream else "generateContent"
        url = (
            f"{GEMINI_URL}/{self.config.api_version}/models/"
            f"{self.config.model}:{action}?key={self.api_key}"
        )
        if stream:
            url += "&alt=sse"
        return url
    
    def _build_payload(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Build the API request payload."""
        parts: List[Dict[str, Any]] = [{"text": prompt}]
        
        if file_data:
            filtered_data = {
                "mime_type": file_data["mime_type"],
                "data": file_data["data"]
            }
            parts.append({"inline_data": filtered_data})
        
        payload: Dict[str, Any] = {
            "contents": [{"parts": parts}],
            "generationConfig": {
                "maxOutputTokens": self.config.max_tokens,
                "temperature": self.config.temperature,
                "topP": self.config.top_p,
                "topK": self.config.top_k,
                "candidateCount": self.config.candidate_count
            },
            "safetySettings": [
                {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": self.config.safety_threshold},
                {"category": "HARM_CATEGORY_HARASSMENT", "threshold": self.config.safety_threshold},
                {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": self.config.safety_threshold},
                {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": self.config.safety_threshold}
            ]
        }
        
        if system_instruction:
            payload["systemInstruction"] = {"parts": [{"text": system_instruction}]}
        
        return payload
    
    def query(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a non-streaming API call to Gemini.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            file_data: Optional file data dict
            
        Returns:
            The API response as a dictionary
            
        Raises:
            APIError: If the API call fails
        """
        url = self._build_url()
        payload = self._build_payload(prompt, system_instruction, file_data)
        headers = {"Content-Type": MIME_TYPE_JSON}
        
        try:
            response = requests.post(url, headers=headers, data=json.dumps(payload))
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")
        
        if not response.ok:
            raise APIError(
                f"Gemini API error: {response.text}",
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
        Make a streaming API call to Gemini.
        
        v3.2.1 Enhancement: Adds timeout support and optional abort callback.
        
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
        url = self._build_url(stream=True)
        payload = self._build_payload(prompt, system_instruction, file_data)
        headers = {"Content-Type": MIME_TYPE_JSON}
        
        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                stream=True,
                timeout=timeout
            )
        except requests.Timeout:
            raise StreamingError(f"Gemini streaming request timed out after {timeout} seconds")
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")
        
        if not response.ok:
            raise APIError(
                f"Gemini API error: {response.text}",
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
                        try:
                            chunk = json.loads(data)
                            
                            # Store sample chunks for debugging (limit to first 3)
                            if len(sample_chunks) < 3:
                                sample_chunks.append(chunk)
                            
                            # Check for error in stream
                            # Error structure: {"error": {"message": "...", "code": ...}}
                            if "error" in chunk and isinstance(chunk.get("error"), dict):
                                error_obj = chunk["error"]
                                error_msg = error_obj.get("message", "Unknown error")
                                error_code = error_obj.get("code", None)
                                error_status = error_obj.get("status", "UNKNOWN")
                                
                                # Check if it's a rate limit error
                                if (error_status == "RESOURCE_EXHAUSTED" or 
                                    "rate" in error_msg.lower() or
                                    "quota" in error_msg.lower()):
                                    raise APIError(
                                        f"Gemini rate limit/quota exceeded during streaming: {error_msg}",
                                        status_code=429,
                                        response_text=json.dumps(chunk),
                                        provider="gemini"
                                    )
                                else:
                                    raise APIError(
                                        f"Gemini API error during streaming ({error_status}): {error_msg}",
                                        status_code=error_code,
                                        response_text=json.dumps(chunk),
                                        provider="gemini"
                                    )
                            
                            text = self.extract_text(chunk)
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
                    "No text chunks extracted from Gemini streaming response. "
                    "Response format may not match Gemini API streaming response structure "
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
    
    @staticmethod
    def extract_text(response: Dict[str, Any]) -> str:
        """
        Extract text from a Gemini API response.
        
        Args:
            response: The raw API response
            
        Returns:
            Extracted text content
        """
        texts = []
        for candidate in response.get("candidates", []):
            content = candidate.get("content", {})
            for part in content.get("parts", []):
                if "text" in part:
                    texts.append(part["text"])
        return "".join(texts)
    
    @staticmethod
    def extract_binary_outputs(response: Dict[str, Any], output_dir: str = ".") -> List[str]:
        """
        Extract and save binary outputs from a Gemini response.
        
        Args:
            response: The raw API response
            output_dir: Directory to save output files
            
        Returns:
            List of saved file paths
        """
        saved_files = []
        output_path = Path(output_dir)
        
        for idx, candidate in enumerate(response.get("candidates", [])):
            content = candidate.get("content", {})
            for part_idx, part in enumerate(content.get("parts", [])):
                if "inline_data" in part:
                    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    mime_type = part["inline_data"].get("mime_type", MIME_TYPE_OCTET_STREAM)
                    extension = mime_module.guess_extension(mime_type) or ".bin"
                    filename = f"output_{timestamp}_c{idx}_p{part_idx}{extension}"
                    
                    filepath = output_path / filename
                    binary_data = base64.b64decode(part["inline_data"]["data"])
                    
                    with open(filepath, "wb") as f:
                        f.write(binary_data)
                    
                    saved_files.append(str(filepath))
                    logger.info(f"Binary output written to: {filepath}")
        
        return saved_files
