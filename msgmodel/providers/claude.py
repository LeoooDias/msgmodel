"""
msgmodel.providers.claude
~~~~~~~~~~~~~~~~~~~~~~~~~

Anthropic Claude API provider implementation.
"""

import logging
from typing import Optional, Dict, Any, List, Iterator

from ..config import ClaudeConfig
from ..exceptions import APIError, ProviderError, StreamingError

logger = logging.getLogger(__name__)

MIME_TYPE_PDF = "application/pdf"


def _get_anthropic_client(api_key: str):
    """
    Get an Anthropic client, raising a clear error if not installed.
    
    Args:
        api_key: Anthropic API key
        
    Returns:
        Anthropic client instance
        
    Raises:
        ProviderError: If anthropic package is not installed
    """
    try:
        from anthropic import Anthropic
        return Anthropic(api_key=api_key)
    except ImportError:
        raise ProviderError(
            "anthropic package not installed. Install with: pip install anthropic"
        )


class ClaudeProvider:
    """
    Anthropic Claude API provider for making LLM requests.
    
    Handles API calls and response parsing for Claude models.
    """
    
    def __init__(self, api_key: str, config: Optional[ClaudeConfig] = None):
        """
        Initialize the Claude provider.
        
        Args:
            api_key: Anthropic API key
            config: Optional configuration (uses defaults if not provided)
        """
        self.api_key = api_key
        self.config = config or ClaudeConfig()
        self._client = None
    
    @property
    def client(self):
        """Lazy-load the Anthropic client."""
        if self._client is None:
            self._client = _get_anthropic_client(self.api_key)
        return self._client
    
    def _build_content(
        self,
        prompt: str,
        file_data: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """Build the content array for the API request."""
        content: List[Dict[str, Any]] = []
        
        if file_data:
            mime_type = file_data["mime_type"]
            data = file_data["data"]
            
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
            "text": prompt
        })
        
        return content
    
    def _build_kwargs(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None,
        stream: bool = False
    ) -> Dict[str, Any]:
        """Build the API request kwargs."""
        content = self._build_content(prompt, file_data)
        
        kwargs: Dict[str, Any] = {
            "model": self.config.model,
            "max_tokens": self.config.max_tokens,
            "messages": [{"role": "user", "content": content}],
            "temperature": self.config.temperature,
            "top_p": self.config.top_p,
            "top_k": self.config.top_k,
        }
        
        if system_instruction:
            kwargs["system"] = system_instruction
        
        if not self.config.cache_control:
            kwargs["metadata"] = {"user_id": "privacy-mode"}
        
        if stream:
            kwargs["stream"] = True
        
        return kwargs
    
    def query(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Make a non-streaming API call to Claude.
        
        Args:
            prompt: The user prompt
            system_instruction: Optional system instruction
            file_data: Optional file data dict
            
        Returns:
            The API response as a dictionary
            
        Raises:
            APIError: If the API call fails
        """
        kwargs = self._build_kwargs(prompt, system_instruction, file_data)
        
        try:
            response = self.client.messages.create(**kwargs)
        except Exception as e:
            raise APIError(f"Claude API error: {e}")
        
        return {
            "id": response.id,
            "model": response.model,
            "role": response.role,
            "content": [
                {
                    "type": block.type,
                    "text": block.text if hasattr(block, "text") else None
                }
                for block in response.content
            ],
            "stop_reason": response.stop_reason,
            "usage": {
                "input_tokens": response.usage.input_tokens,
                "output_tokens": response.usage.output_tokens
            }
        }
    
    def stream(
        self,
        prompt: str,
        system_instruction: Optional[str] = None,
        file_data: Optional[Dict[str, Any]] = None
    ) -> Iterator[str]:
        """
        Make a streaming API call to Claude.
        
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
        kwargs = self._build_kwargs(prompt, system_instruction, file_data)
        
        try:
            with self.client.messages.stream(**kwargs) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            if "anthropic" in str(type(e).__module__):
                raise APIError(f"Claude API error: {e}")
            raise StreamingError(f"Streaming interrupted: {e}")
    
    @staticmethod
    def extract_text(response: Dict[str, Any]) -> str:
        """
        Extract text from a Claude API response.
        
        Args:
            response: The raw API response
            
        Returns:
            Extracted text content
        """
        texts = []
        for block in response.get("content", []):
            if block.get("type") == "text" and block.get("text"):
                texts.append(block["text"])
        return "\n".join(texts)
