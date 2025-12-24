# msgmodel v4.0.1 Release Notes

**Release Date**: December 21, 2025  
**Status**: Stable  
**Breaking Changes**: None

---

## Overview

v4.0.1 is a maintenance and feature enhancement release that completes the privacy information pipeline across all msgmodel APIs (sync, async, and CLI). No breaking changes have been introduced—all existing code will continue to work unchanged.

---

## What's New

### 🔒 Privacy Metadata Pipeline - Complete Implementation

The privacy information system introduced in v4.0.0 has been fully wired end-to-end across all routes:

#### **1. Async API Now Includes Privacy Information**
Previously, `aquery()` and `astream()` were not returning privacy metadata, creating an inconsistency with the sync API.

**Fixed in v4.0.1:**
- `async_core.aquery()` now populates the `privacy` field in `LLMResponse`
- Both OpenAI and Gemini async implementations return complete privacy metadata
- Anthropic async support (if implemented) will also include privacy metadata

**Example:**
```python
import asyncio
from msgmodel import aquery

async def check_privacy():
    response = await aquery("openai", "Hello!")
    print(response.privacy)
    # Output:
    # {
    #     "provider": "openai",
    #     "training_retention": False,
    #     "data_retention": "None (Zero Data Retention header sent)",
    #     "enforcement_level": "default",
    #     "special_conditions": "ZDR header sent automatically",
    #     "reference": "https://platform.openai.com/docs/guides/zero-data-retention"
    # }

asyncio.run(check_privacy())
```

#### **2. CLI Now Displays Privacy Information**
The command-line interface can now show privacy guarantees for requests.

**Usage - Verbose Mode:**
```bash
python -m msgmodel -p openai "Hello!" --verbose
```

**Output includes:**
```
Hello!
[INFO] Model: gpt-4o
[INFO] Provider: openai
[INFO] Privacy Guarantee for this Request:
  Provider: OPENAI
  Training Retention: NOT retained for training
  Data Retention: None (Zero Data Retention header sent)
  Enforcement Level: default
  Special Conditions: ZDR header sent automatically with all requests.
  Reference: https://platform.openai.com/docs/guides/zero-data-retention
```

**Privacy Notice (Always Shown):**
When privacy information is available but `--verbose` is not used:
```
[INFO] Use --verbose to see privacy guarantees for this provider
```

#### **3. All Three Providers Have Privacy Metadata**

| Provider | Training Retention | Data Retention | Privacy Link |
|----------|-------------------|----------------|--------------|
| **OpenAI** | ❌ No (ZDR enforced) | None | [Zero Data Retention](https://platform.openai.com/docs/guides/zero-data-retention) |
| **Gemini** | ⚠️ Tier-dependent | Varies (24-72h paid, training on free) | [Gemini API Terms](https://ai.google.dev/gemini-api/terms) |
| **Anthropic** | ❌ No (default) | Temporary (safety monitoring) | [Privacy Policy](https://www.anthropic.com/legal/privacy) |

---

## Bug Fixes

### Async API Privacy Metadata Missing
- **Issue**: The `aquery()` function was not returning privacy metadata, even though it was properly structured in the `LLMResponse` dataclass and implemented in sync `query()`
- **Root Cause**: Design oversight—infrastructure was in place but async implementations weren't calling `get_privacy_info()`
- **Solution**: Added privacy metadata collection to both `_aquery_openai()` and `_aquery_gemini()` helper functions

---

## Migration Guide

### For Existing Code

**No changes required.** The `privacy` field in `LLMResponse` is optional and defaults to `None` if not populated. Existing code that doesn't use privacy information will continue to work exactly as before.

### To Enable Privacy Display

#### **Sync API:**
```python
from msgmodel import query

response = query("openai", "Your prompt here")

if response.privacy:
    print(f"Provider: {response.privacy['provider']}")
    print(f"Training Retention: {response.privacy['training_retention']}")
    print(f"Reference: {response.privacy['reference']}")
```

#### **Async API:**
```python
import asyncio
from msgmodel import aquery

async def main():
    response = await aquery("gemini", "Your prompt here")
    
    if response.privacy:
        tier = response.privacy['training_retention']
        print(f"Gemini tier-dependent: {tier}")

asyncio.run(main())
```

#### **CLI:**
```bash
# Show privacy guarantees
python -m msgmodel -p anthropic "Your prompt" --verbose

# Compare privacy across providers
for provider in openai gemini anthropic; do
    echo "=== $provider ===" 
    python -m msgmodel -p $provider "test" --verbose 2>&1 | grep -A 10 "Privacy Guarantee"
done
```

---

## Technical Details

### Architecture

Privacy metadata flows through the system as:
```
Provider.get_privacy_info() [static method]
        ↓
LLMResponse.privacy field [optional dict]
        ↓
CLI format_privacy_info() [human-readable output]
```

### Privacy Field Structure

All providers return a dictionary with these keys:
```python
{
    "provider": str,                    # "openai", "gemini", "anthropic"
    "training_retention": bool|str,     # False, True, or "depends_on_tier"
    "data_retention": str,              # Human-readable retention policy
    "enforcement_level": str,           # "default" or "tier_dependent"
    "special_conditions": str,          # Additional context
    "reference": str                    # Official policy documentation link
}
```

### Test Coverage

All new functionality is covered by comprehensive tests:
- **9 CLI privacy tests** - formatting, verbose display, JSON output, edge cases
- **4 async privacy tests** - OpenAI and Gemini privacy metadata returns
- **100% code coverage maintained** - all 416 tests passing

---

## Important Notes

### Privacy Information is Reference Material
The privacy metadata returned by msgmodel is informational and based on each provider's published policies. For authoritative information:
- **OpenAI**: Review [Zero Data Retention documentation](https://platform.openai.com/docs/guides/zero-data-retention)
- **Gemini**: Check [Gemini API Terms](https://ai.google.dev/gemini-api/terms)
- **Anthropic**: See [Anthropic Privacy Policy](https://www.anthropic.com/legal/privacy)

### msgmodel Itself Remains Stateless
Remember: **msgmodel never stores or retains your data.** Each request is ephemeral and independent. The privacy information indicates how the LLM providers handle your data.

---

## Installation & Upgrade

```bash
# Upgrade from any 4.0.x version
pip install --upgrade msgmodel

# Or explicitly
pip install msgmodel==4.0.1
```

---

## Changelog Summary

| Component | Change | Type |
|-----------|--------|------|
| `async_core.py` | Added privacy metadata to aquery returns | Bug Fix |
| `__main__.py` | Added privacy display to CLI | Feature |
| `test_cli.py` | Added 9 new privacy tests | Test Coverage |
| `test_async_core_privacy.py` | Added 4 new async privacy tests | Test Coverage |

---

## Getting Help

- **Questions about privacy?** Check the provider's official documentation links in the privacy metadata
- **Issues or bugs?** Report on [GitHub Issues](https://github.com/your-repo/issues)
- **Documentation?** See [msgmodel docs](../INDEX.md)

---

## What's Next (v4.1 Roadmap)

Planned improvements for future releases:
- [ ] Extend async support to Anthropic provider
- [ ] Cache privacy metadata to reduce repeated lookups
- [ ] Add privacy compliance reporting tools
- [ ] Implement per-provider encryption options

---

**msgmodel v4.0.1** - Privacy-first, open, and fully transparent. 🔐
