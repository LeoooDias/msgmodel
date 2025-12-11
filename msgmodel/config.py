"""
msgmodel.config
~~~~~~~~~~~~~~~

Configuration dataclasses for LLM providers.

These classes provide type-safe, runtime-configurable settings
for each supported provider. Defaults match the original script's
hardcoded values.
"""

from dataclasses import dataclass, field
from typing import Optional, List
from enum import Enum


class Provider(str, Enum):
    """Supported LLM providers."""
    OPENAI = "openai"
    GEMINI = "gemini"
    CLAUDE = "claude"
    
    @classmethod
    def from_string(cls, value: str) -> "Provider":
        """
        Convert string to Provider enum.
        
        Args:
            value: Provider name or shorthand ('o', 'g', 'c', 'openai', 'gemini', 'claude')
            
        Returns:
            Provider enum member
            
        Raises:
            ValueError: If the value is not a valid provider
        """
        value = value.lower().strip()
        
        # Support shorthand codes
        shortcuts = {
            'o': cls.OPENAI,
            'g': cls.GEMINI,
            'c': cls.CLAUDE,
        }
        
        if value in shortcuts:
            return shortcuts[value]
        
        # Support full names
        for provider in cls:
            if provider.value == value:
                return provider
        
        valid = ", ".join([f"'{p.value}'" for p in cls] + ["'o'", "'g'", "'c'"])
        raise ValueError(f"Invalid provider '{value}'. Valid options: {valid}")


# ============================================================================
# API URLs (constants, not configurable per-request)
# ============================================================================
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENAI_FILES_URL = "https://api.openai.com/v1/files"
GEMINI_URL = "https://generativelanguage.googleapis.com"
CLAUDE_URL = "https://api.anthropic.com"

# Environment variable names for API keys
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
GEMINI_API_KEY_ENV = "GEMINI_API_KEY"  
CLAUDE_API_KEY_ENV = "ANTHROPIC_API_KEY"

# Default API key file names (for backward compatibility)
OPENAI_API_KEY_FILE = "openai-api.key"
GEMINI_API_KEY_FILE = "gemini-api.key"
CLAUDE_API_KEY_FILE = "claude-api.key"


@dataclass
class OpenAIConfig:
    """
    Configuration for OpenAI API calls.
    
    Attributes:
        model: Model identifier (e.g., 'gpt-4o', 'gpt-4o-mini')
        temperature: Sampling temperature (0.0 to 2.0)
        top_p: Nucleus sampling parameter
        max_tokens: Maximum tokens to generate
        n: Number of completions to generate
        store_data: Whether to allow OpenAI to store the data
        delete_files_after_use: Whether to delete uploaded files after use
    """
    model: str = "gpt-4o"
    temperature: float = 1.0
    top_p: float = 1.0
    max_tokens: int = 1000
    n: int = 1
    store_data: bool = False
    delete_files_after_use: bool = True


@dataclass
class GeminiConfig:
    """
    Configuration for Google Gemini API calls.
    
    Attributes:
        model: Model identifier (e.g., 'gemini-2.5-flash', 'gemini-1.5-pro')
        temperature: Sampling temperature (0.0 to 2.0)
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        max_tokens: Maximum tokens to generate
        candidate_count: Number of response candidates
        safety_threshold: Content safety filtering level
        api_version: API version to use
        cache_control: Whether to enable caching
    """
    model: str = "gemini-2.5-flash"
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 40
    max_tokens: int = 1000
    candidate_count: int = 1
    safety_threshold: str = "BLOCK_NONE"
    api_version: str = "v1beta"
    cache_control: bool = False


@dataclass
class ClaudeConfig:
    """
    Configuration for Anthropic Claude API calls.
    
    Attributes:
        model: Model identifier (e.g., 'claude-sonnet-4-20250514', 'claude-3-opus-20240229')
        temperature: Sampling temperature (0.0 to 1.0)
        top_p: Nucleus sampling parameter
        top_k: Top-k sampling parameter
        max_tokens: Maximum tokens to generate
        cache_control: Whether to enable caching
    """
    model: str = "claude-sonnet-4-20250514"
    temperature: float = 1.0
    top_p: float = 0.95
    top_k: int = 40
    max_tokens: int = 1000
    cache_control: bool = False


# Type alias for any config
ProviderConfig = OpenAIConfig | GeminiConfig | ClaudeConfig


def get_default_config(provider: Provider) -> ProviderConfig:
    """
    Get the default configuration for a provider.
    
    Args:
        provider: The LLM provider
        
    Returns:
        Default configuration dataclass for the provider
    """
    configs = {
        Provider.OPENAI: OpenAIConfig,
        Provider.GEMINI: GeminiConfig,
        Provider.CLAUDE: ClaudeConfig,
    }
    return configs[provider]()
