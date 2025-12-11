"""
msgmodel.providers.openai
~~~~~~~~~~~~~~~~~~~~~~~~~

OpenAI API provider implementation.
"""

import json
import base64
import logging
from typing import Optional, Dict, Any, List, Iterator

import requests

from ..config import OpenAIConfig, OPENAI_URL, OPENAI_FILES_URL
from ..exceptions import APIError, ProviderError, StreamingError

logger = logging.getLogger(__name__)

# MIME type constants
MIME_TYPE_JSON = "application/json"
MIME_TYPE_PDF = "application/pdf"


class OpenAIProvider:
    """
    OpenAI API provider for making LLM requests.
    
    Handles file uploads, API calls, and response parsing for OpenAI models.
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
        self._uploaded_file_ids: List[str] = []
    
    def upload_file(self, file_path: str, purpose: str = "assistants") -> str:
        """
        Upload a file to OpenAI Files API.
        
        Args:
            file_path: Path to the file to upload
            purpose: Purpose of the upload
            
        Returns:
            The file ID assigned by OpenAI
            
        Raises:
            APIError: If the upload fails
        """
        from pathlib import Path
        
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            with open(file_path, "rb") as f:
                files = {"file": (Path(file_path).name, f)}
                data = {"purpose": purpose}
                response = requests.post(
                    OPENAI_FILES_URL, 
                    headers=headers, 
                    files=files, 
                    data=data
                )
        except IOError as e:
            raise APIError(f"Failed to read file for upload: {e}")
        
        if not response.ok:
            raise APIError(
                f"File upload failed: {response.text}",
                status_code=response.status_code,
                response_text=response.text
            )
        
        file_id = response.json().get("id")
        self._uploaded_file_ids.append(file_id)
        return file_id
    
    def delete_file(self, file_id: str) -> bool:
        """
        Delete a file from OpenAI Files API.
        
        Args:
            file_id: The file ID to delete
            
        Returns:
            True if deletion was successful
        """
        url = f"{OPENAI_FILES_URL}/{file_id}"
        headers = {"Authorization": f"Bearer {self.api_key}"}
        
        try:
            response = requests.delete(url, headers=headers)
            if response.ok:
                if file_id in self._uploaded_file_ids:
                    self._uploaded_file_ids.remove(file_id)
                return True
            else:
                logger.warning(f"Failed to delete file {file_id}: {response.text}")
                return False
        except requests.RequestException as e:
            logger.warning(f"Request exception while deleting file {file_id}: {e}")
            return False
    
    def cleanup(self) -> None:
        """Delete all uploaded files if configured to do so."""
        if self.config.delete_files_after_use:
            for file_id in list(self._uploaded_file_ids):
                if self.delete_file(file_id):
                    logger.info(f"Deleted uploaded file {file_id}")
    
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
            file_id = file_data.get("file_id")
            
            if mime_type.startswith("image/"):
                content.append({
                    "type": "input_image",
                    "image_url": f"data:{mime_type};base64,{encoded_data}"
                })
            elif mime_type == MIME_TYPE_PDF:
                if not file_id:
                    raise ProviderError("PDF provided without uploaded file_id")
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
            "text": prompt
        })
        
        return content
    
    def _build_payload(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Build the API request payload."""
        content = self._build_content(prompt, file_data)
        
        payload: Dict[str, Any] = {
            "model": self.config.model,
            "input": [{"role": "user", "content": content}],
            "max_output_tokens": self.config.max_tokens,
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
        }
        
        if system_instruction:
            payload["instructions"] = system_instruction
        
        if not self.config.store_data:
            payload["store"] = False
        
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
        headers = {
            "Content-Type": MIME_TYPE_JSON,
            "Authorization": f"Bearer {self.api_key}"
        }
        
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
        file_data: Optional[Dict[str, Any]] = None
    ) -> Iterator[str]:
        """
        Make a streaming API call to OpenAI.
        
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
        payload = self._build_payload(prompt, system_instruction, file_data, stream=True)
        headers = {
            "Content-Type": MIME_TYPE_JSON,
            "Authorization": f"Bearer {self.api_key}"
        }
        
        try:
            response = requests.post(
                OPENAI_URL,
                headers=headers,
                data=json.dumps(payload),
                stream=True
            )
        except requests.RequestException as e:
            raise APIError(f"Request failed: {e}")
        
        if not response.ok:
            raise APIError(
                f"OpenAI API error: {response.text}",
                status_code=response.status_code,
                response_text=response.text
            )
        
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
                            # Extract text from streaming response
                            if "delta" in chunk:
                                delta = chunk["delta"]
                                if isinstance(delta, dict) and "text" in delta:
                                    yield delta["text"]
                            elif "output" in chunk:
                                for item in chunk.get("output", []):
                                    for c in item.get("content", []):
                                        if c.get("type") == "output_text":
                                            yield c.get("text", "")
                        except json.JSONDecodeError:
                            continue
        except Exception as e:
            raise StreamingError(f"Streaming interrupted: {e}")
    
    @staticmethod
    def extract_text(response: Dict[str, Any]) -> str:
        """
        Extract text from an OpenAI API response.
        
        Args:
            response: The raw API response
            
        Returns:
            Extracted text content
        """
        if "output_text" in response:
            return response["output_text"]
        
        if "output" in response and response["output"]:
            texts = []
            for item in response["output"]:
                for c in item.get("content", []):
                    if c.get("type") == "output_text":
                        texts.append(c.get("text", ""))
            return "\n".join(t for t in texts if t)
        
        return ""
