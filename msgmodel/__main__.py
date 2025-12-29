"""
msgmodel CLI
~~~~~~~~~~~~

Command-line interface for msgmodel.

Usage:
    python -m msgmodel --provider openai --prompt "Hello, world!"
    python -m msgmodel -p g -f prompt.txt --stream
"""

import argparse
import sys
import io
import logging
from pathlib import Path
from typing import Optional, Dict, Any

from . import (
    __version__,
    query,
    stream,
    Provider,
    OpenAIConfig,
    GeminiConfig,
    AnthropicConfig,
    ClaudeConfig,
    MsgModelError,
    ConfigurationError,
    AuthenticationError,
    FileError,
    APIError,
)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
    stream=sys.stderr,
)
logger = logging.getLogger(__name__)


def format_privacy_info(privacy: Optional[Dict[str, Any]]) -> str:
    """
    Format privacy metadata into a human-readable string.
    
    Args:
        privacy: Privacy metadata dictionary from LLMResponse
        
    Returns:
        Formatted string with privacy information
    """
    if not privacy:
        return "Privacy information unavailable"
    
    lines = ["Privacy Information for this Request:"]
    
    if "provider" in privacy:
        provider_name = privacy["provider"].upper()
        lines.append(f"  Provider: {provider_name}")
    
    if "training_retention" in privacy:
        training = privacy["training_retention"]
        if isinstance(training, bool):
            training_str = "NOT retained for training" if not training else "May be retained for training"
        else:
            training_str = str(training)
        lines.append(f"  Training Retention: {training_str}")
    
    if "data_retention" in privacy:
        lines.append(f"  Data Retention: {privacy['data_retention']}")
    
    if "enforcement_level" in privacy:
        lines.append(f"  Enforcement Level: {privacy['enforcement_level']}")
    
    if "special_conditions" in privacy:
        lines.append(f"  Special Conditions: {privacy['special_conditions']}")
    
    if "reference" in privacy:
        lines.append(f"  Reference: {privacy['reference']}")
    
    return "\n".join(lines)


logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        prog="msgmodel",
        description="Unified LLM API - Query OpenAI, Gemini, or Claude from the command line.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s -p openai "Hello, world!"
  %(prog)s -p gemini -f prompt.txt
  %(prog)s -p claude "Tell me a story" --stream
  %(prog)s -p o "Analyze this" -i instructions.txt -f image.jpg
""",
    )
    
    parser.add_argument(
        "-p", "--provider",
        required=True,
        help="LLM provider: 'openai'/'o', 'gemini'/'g', 'anthropic'/'a', or 'claude'/'c'",
    )
    
    parser.add_argument(
        "prompt",
        nargs="?",
        help="The prompt text (or use -f for file input)",
    )
    
    parser.add_argument(
        "-f", "--file",
        help="Path to file to attach (image, PDF, text file, etc.) - file content is included in the request to the LLM",
    )
    
    parser.add_argument(
        "-i", "--instruction",
        help="System instruction (text or path to file)",
    )
    
    parser.add_argument(
        "-k", "--api-key",
        help="API key (overrides environment variable and key file)",
    )
    
    parser.add_argument(
        "-m", "--model",
        help="Model to use (overrides default)",
    )
    
    parser.add_argument(
        "-t", "--max-tokens",
        type=int,
        default=1000,
        help="Maximum tokens to generate (default: 1000)",
    )
    
    parser.add_argument(
        "--temperature",
        type=float,
        help="Sampling temperature (0.0 to 2.0)",
    )
    
    parser.add_argument(
        "-s", "--stream",
        action="store_true",
        help="Stream the response",
    )
    
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output raw JSON response",
    )
    
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    
    return parser.parse_args()


def read_file_content(path: str) -> str:
    """Read content from a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except IOError as e:
        raise FileError(f"Cannot read file {path}: {e}")


def main() -> int:
    """Main entry point for the CLI."""
    args = parse_args()
    
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)
    
    try:
        # Get the prompt
        if not args.prompt:
            logger.error("Prompt text is required")
            return 1
        
        prompt = args.prompt
        
        # Get system instruction
        system_instruction = None
        if args.instruction:
            # Check if it's a file path
            if Path(args.instruction).exists():
                system_instruction = read_file_content(args.instruction)
            else:
                system_instruction = args.instruction
        
        # Prepare file attachment if provided
        file_like = None
        filename = None
        if args.file:
            file_path = Path(args.file)
            if not file_path.exists():
                raise FileError(f"File not found: {args.file}")
            
            # Read file into BytesIO
            with open(file_path, "rb") as f:
                file_bytes = f.read()
            file_like = io.BytesIO(file_bytes)
            filename = file_path.name
        
        # Common kwargs
        kwargs = {
            "provider": args.provider,
            "prompt": prompt,
            "api_key": args.api_key,
            "system_instruction": system_instruction,
            "file_like": file_like,
            "filename": filename,
            "max_tokens": args.max_tokens,
            "model": args.model,
            "temperature": args.temperature,
        }
        
        if args.stream:
            # Streaming mode
            for chunk in stream(**kwargs):
                print(chunk, end="", flush=True)
            print()  # Final newline
        else:
            # Non-streaming mode
            response = query(**kwargs)
            
            if args.json:
                import json
                print(json.dumps(response.raw_response, indent=2))
            else:
                print(response.text)
                
                if args.verbose:
                    logger.info(f"Model: {response.model}")
                    logger.info(f"Provider: {response.provider}")
                    if response.usage:
                        logger.info(f"Usage: {response.usage}")
                    if response.privacy:
                        privacy_str = format_privacy_info(response.privacy)
                        logger.info(privacy_str)
                else:
                    # Always show privacy info notice, even without verbose flag
                    if response.privacy:
                        logger.info("Use --verbose to see privacy information for this provider")
        
        return 0
        
    except ConfigurationError as e:
        logger.error(f"Configuration error: {e}")
        return 1
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        return 2
    except FileError as e:
        logger.error(f"File error: {e}")
        return 3
    except APIError as e:
        logger.error(f"API error: {e}")
        return 4
    except MsgModelError as e:
        logger.error(f"Error: {e}")
        return 5
    except KeyboardInterrupt:
        logger.info("\nOperation cancelled")
        return 0


if __name__ == "__main__":
    sys.exit(main())
