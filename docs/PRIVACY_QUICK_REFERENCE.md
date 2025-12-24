# Quick Reference: Privacy Metadata in msgmodel v4.0.1

## TL;DR

✅ **No breaking changes**  
✅ **Privacy info now available in async API**  
✅ **CLI can display privacy guarantees**  
✅ **100% test coverage maintained**

---

## Using Privacy Information

### Sync API (Unchanged)
```python
from msgmodel import query

response = query("openai", "Hello")
print(response.privacy["provider"])           # "openai"
print(response.privacy["training_retention"]) # False
print(response.privacy["reference"])          # URL to policy
```

### Async API (New in 4.0.1)
```python
import asyncio
from msgmodel import aquery

async def main():
    response = await aquery("openai", "Hello")
    print(response.privacy)  # Now populated! (was None in < 4.0.1)

asyncio.run(main())
```

### CLI (New in 4.0.1)
```bash
# Show privacy guarantees
python -m msgmodel -p openai "Hello" --verbose

# Output shows:
# - Provider name and capabilities
# - Training retention policy
# - Data retention duration
# - Link to official policy
```

---

## Privacy Field Contents

```python
response.privacy = {
    "provider": "openai",                              # str
    "training_retention": False,                       # bool or "depends_on_tier"
    "data_retention": "None (ZDR header sent)",       # str
    "enforcement_level": "default",                    # str
    "special_conditions": "ZDR header sent auto...",  # str
    "reference": "https://platform.openai.com/..."    # URL
}
```

---

## Provider Privacy Summary

| Provider | Training? | Retention | Recommendation |
|----------|-----------|-----------|-----------------|
| 🔒 **OpenAI** | ❌ No | None | ✅ Most private |
| ⚠️ **Gemini** | Depends | Tier-dependent | Use paid tier for privacy |
| 🔐 **Anthropic** | ❌ No | Temporary | ✅ Good privacy |

---

## Migration Checklist

- [ ] Upgrade: `pip install --upgrade msgmodel`
- [ ] Optional: Use new privacy features
- [ ] No code changes required for existing functionality
- [ ] No new dependencies added

---

## Testing

All changes fully tested:
- ✅ 416 tests passing
- ✅ 100% code coverage
- ✅ 13 new tests for privacy features
- ✅ All async operations verified
- ✅ CLI output validated

---

## Support

- **API Docs**: `LLMResponse.privacy` field
- **Release Notes**: `docs/RELEASE_NOTES_v4.0.1.md`
- **Implementation**: `docs/V4_0_1_IMPLEMENTATION_COMPLETE.md`
- **Tests**: `tests/test_cli.py`, `tests/test_async_core_privacy.py`

---

## Questions?

Refer to official provider policies:
- [OpenAI Zero Data Retention](https://platform.openai.com/docs/guides/zero-data-retention)
- [Gemini API Terms](https://ai.google.dev/gemini-api/terms)
- [Anthropic Privacy](https://www.anthropic.com/legal/privacy)
