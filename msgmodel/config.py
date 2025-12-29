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
    ANTHROPIC = "anthropic"
    
    @classmethod
    def from_string(cls, value: str) -> "Provider":
        """
        Convert string to Provider enum.
        
        Args:
            value: Provider name or shorthand ('o', 'g', 'a', 'openai', 'gemini', 'anthropic')
            
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
            'a': cls.ANTHROPIC,
            'c': cls.ANTHROPIC,  # 'claude' shorthand
        }
        
        if value in shortcuts:
            return shortcuts[value]
        
        # Support full names and aliases
        aliases = {
            'claude': cls.ANTHROPIC,
        }
        if value in aliases:
            return aliases[value]
        
        for provider in cls:
            if provider.value == value:
                return provider
        
        valid = ", ".join([f"'{p.value}'" for p in cls] + ["'o'", "'g'", "'a'", "'c'", "'claude'"])
        raise ValueError(f"Invalid provider '{value}'. Valid options: {valid}")


# ============================================================================
# API URLs (constants, not configurable per-request)
# ============================================================================
OPENAI_URL = "https://api.openai.com/v1/chat/completions"
GEMINI_URL = "https://generativelanguage.googleapis.com"
ANTHROPIC_URL = "https://api.anthropic.com/v1/messages"

# Environment variable names for API keys
OPENAI_API_KEY_ENV = "OPENAI_API_KEY"
GEMINI_API_KEY_ENV = "GOOGLE_API_KEY"
ANTHROPIC_API_KEY_ENV = "ANTHROPIC_API_KEY"

# Default API key file names (for backward compatibility)
OPENAI_API_KEY_FILE = "openai-api.key"
GEMINI_API_KEY_FILE = "gemini-api.key"
ANTHROPIC_API_KEY_FILE = "anthropic-api.key"


@dataclass
class OpenAIConfig:
    """
    Configuration for OpenAI API calls.
    
    OpenAI does not use API data for model training (standard policy for all API users).
    The X-OpenAI-No-Store header is also sent to request zero data storage, but actual
    Zero Data Retention (ZDR) requires separate eligibility from OpenAI.
    See: https://platform.openai.com/docs/models/how-we-use-your-data
    
    Attributes:
        model: Model identifier (e.g., 'gpt-4o', 'gpt-4o-mini')
        temperature: Sampling temperature (0.0 to 2.0)
        top_p: Nucleus sampling parameter
        max_tokens: Maximum tokens to generate
        n: Number of completions to generate
        api_key: Optional API key. If provided, overrides environment variable.
    
    Note: File uploads are only supported via inline base64-encoding in prompts.
    Files are limited to practical API size constraints (~15-20MB).
    """
    model: str = "gpt-4o"
    temperature: float = 1.0
    top_p: float = 1.0
    max_tokens: int = 1000
    n: int = 1
    api_key: Optional[str] = None


@dataclass
class GeminiConfig:
    """
    Configuration for Google Gemini API calls.
    
    IMPORTANT: Data handling depends entirely on your Google account tier.
    msgmodel cannot detect or control which tier you're using.
    
    - Paid tier (Cloud Billing): Data NOT used for training; temporary abuse monitoring only
    - Free tier: Data MAY be used for model training
    
    Verify your tier directly with Google if privacy is important for your use case.
    See: https://ai.google.dev/gemini-api/terms
    
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
        api_key: Optional API key. If provided, overrides environment variable.
    
    Note: File uploads are only supported via inline base64-encoding in prompts.
    Files are limited to practical API size constraints (~22MB).
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
    api_key: Optional[str] = None


@dataclass
class AnthropicConfig:
    """
    Configuration for Anthropic Claude API calls.
    
    **PRIVACY POLICY**: Claude API does not use prompts or responses for model training.
    Data is retained temporarily for abuse prevention and safety monitoring only.
    
    See: https://www.anthropic.com/legal/privacy-notice
    
    Attributes:
        model: Model identifier (e.g., 'claude-haiku-4-5-20251001', 'claude-sonnet-4-20250514')
        temperature: Sampling temperature (0.0 to 1.0)
        top_p: Nucleus sampling parameter (0.0 to 1.0)
        top_k: Top-k sampling parameter
        max_tokens: Maximum tokens to generate
        api_key: Optional API key. If provided, overrides environment variable.
    
    Note: File uploads are only supported via inline base64-encoding in prompts.
    Files are limited to practical API size constraints (~20MB).
    """
    model: str = "claude-haiku-4-5-20251001"
    temperature: float = 1.0
    top_p: float = 1.0
    top_k: int = 0
    max_tokens: int = 1000
    api_key: Optional[str] = None


# Type alias for supported configs
ProviderConfig = OpenAIConfig | GeminiConfig | AnthropicConfig


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
        Provider.ANTHROPIC: AnthropicConfig,
    }
    return configs[provider]()
