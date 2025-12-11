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
from typing import Optional, Dict, Any, List, Iterator

import requests

from ..config import GeminiConfig, GEMINI_URL
from ..exceptions import APIError, StreamingError

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
        """
        self.api_key = api_key
        self.config = config or GeminiConfig()
    
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
        file_data: Optional[Dict[str, Any]] = None
    ) -> Iterator[str]:
        """
        Make a streaming API call to Gemini.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            file_data: Optional file data dict
            
        Yields:
            Text chunks as they arrive
            
        Raises:
            APIError: If the API call fails
            StreamingError: If streaming fails
        """
        url = self._build_url(stream=True)
        payload = self._build_payload(prompt, system_instruction, file_data)
        headers = {"Content-Type": MIME_TYPE_JSON}
        
        try:
            response = requests.post(
                url,
                headers=headers,
                data=json.dumps(payload),
                stream=True
            )
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")
        
        if not response.ok:
            raise APIError(
                f"Gemini API error: {response.text}",
                status_code=response.status_code,
                response_text=response.text
            )
        
        try:
            for line in response.iter_lines():
                if line:
                    line_text = line.decode("utf-8")
                    if line_text.startswith("data: "):
                        data = line_text[6:]
                        try:
                            chunk = json.loads(data)
                            text = self.extract_text(chunk)
                            if text:
                                yield text
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            raise StreamingError(f"Streaming interrupted: {e}")
    
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
