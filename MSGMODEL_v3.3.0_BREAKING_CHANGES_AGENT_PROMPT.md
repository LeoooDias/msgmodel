# msgmodel v3.3.0 Breaking Changes - AI Dev Agent Prompt

## Overview

If your project uses **msgmodel < v3.3.0** and you're upgrading to **v3.3.0+**, you MUST update your streaming error handling code. This is a **breaking change** that improves error reliability but requires code updates.

## What Changed

### 1. Streaming Now Raises `StreamingError` on Empty Response (BREAKING)

**Before (v3.2.x):**
```python
# This would silently fail with just a log message
for chunk in stream("openai", "prompt"):
    print(chunk, end="")
# If no chunks: silent log, empty iteration
```

**After (v3.3.0+):**
```python
# This now raises StreamingError if chunks_received == 0
for chunk in stream("openai", "prompt"):
    print(chunk, end="")
# If no chunks: raises StreamingError with sample chunks for debugging
```

**Migration Required:**
```python
from msgmodel import stream, StreamingError

try:
    for chunk in stream("openai", "prompt"):
        print(chunk, end="", flush=True)
except StreamingError as e:
    print(f"Stream failed: {e.message}")
    if e.sample_chunks:
        print(f"Debug info: {e.sample_chunks}")
```

### 2. API Errors in Streams Now Raise `APIError` (BREAKING)

**Before (v3.2.x):**
```python
# Rate limits and API errors were silently processed
# Bad chunks were ignored or caused broken iteration
for chunk in stream("openai", "prompt"):
    # If rate limited: broken iteration, corrupted response
    print(chunk, end="")
```

**After (v3.3.0+):**
```python
# Rate limits and API errors now raise APIError immediately
from msgmodel import APIError, RateLimitError

try:
    for chunk in stream("openai", "prompt"):
        print(chunk, end="", flush=True)
except RateLimitError as e:
    # status_code == 429
    print(f"Hit rate limit, retry after {e.retry_after}s")
except APIError as e:
    # Caught other API errors (service unavailable, invalid request, etc.)
    print(f"API error: {e.message} (status: {e.status_code})")
    print(f"Provider: {e.provider}")
```

### 3. Stream Response Structure More Explicit

**Before (v3.2.x):**
- Streaming error messages were logged but didn't include context
- No sample chunks for debugging malformed responses

**After (v3.3.0+):**
- `StreamingError` now includes `sample_chunks` parameter (first 3 chunks)
- Error messages include formatted sample JSON for debugging
- `chunks_received` count available for monitoring

```python
except StreamingError as e:
    print(f"Chunks received before failure: {e.chunks_received}")
    print(f"Sample chunks (for debugging):")
    for i, chunk in enumerate(e.sample_chunks, 1):
        print(f"  Chunk {i}: {chunk}")
```

## Required Code Changes

### Pattern 1: Simple Streaming (Add Try-Except)

**Old Code:**
```python
from msgmodel import stream

response_text = ""
for chunk in stream("openai", "Tell me a story"):
    response_text += chunk
    print(chunk, end="", flush=True)
```

**New Code:**
```python
from msgmodel import stream, StreamingError

response_text = ""
try:
    for chunk in stream("openai", "Tell me a story"):
        response_text += chunk
        print(chunk, end="", flush=True)
except StreamingError as e:
    # Handle empty/malformed streams
    print(f"Error: {e.message}")
    raise  # or handle gracefully
```

### Pattern 2: Streaming with Retry (Handle Rate Limits)

**Old Code:**
```python
from msgmodel import stream

for chunk in stream("openai", "prompt"):
    print(chunk, end="")
```

**New Code:**
```python
from msgmodel import stream, APIError, RateLimitError
import time

max_retries = 3
retry_count = 0

while retry_count < max_retries:
    try:
        for chunk in stream("openai", "prompt"):
            print(chunk, end="", flush=True)
        break  # Success
    except RateLimitError as e:
        retry_count += 1
        if retry_count >= max_retries:
            raise
        wait_time = e.retry_after or (2 ** retry_count)  # Exponential backoff
        print(f"Rate limited. Waiting {wait_time}s...")
        time.sleep(wait_time)
    except APIError as e:
        print(f"API error: {e.message}")
        raise
```

### Pattern 3: Streaming with Abort Callback (No Change Needed)

The v3.2.1 `on_chunk` callback still works the same way:

```python
from msgmodel import stream

def handle_chunk(chunk: str) -> bool:
    print(chunk, end="", flush=True)
    return True  # Continue streaming

try:
    for chunk in stream("openai", "prompt", on_chunk=handle_chunk):
        pass  # chunk already processed by callback
except StreamingError as e:
    print(f"Stream error: {e.message}")
```

## New Utility Methods (Optional)

v3.3.0 adds helper methods for advanced error detection:

```python
from msgmodel.exceptions import StreamingError
import json

def handle_streaming_error(chunk_data):
    """Example: Use StreamingError helpers for custom error detection."""
    error = StreamingError.detect_error_in_chunk(chunk_data)
    
    if error:
        if StreamingError.is_rate_limit_error(error):
            print("Rate limit detected!")
            return "RATE_LIMIT"
        else:
            print("Other API error detected!")
            return "API_ERROR"
    
    return "OK"
```

## Checklist for Migration

When updating code that uses msgmodel v3.3.0:

- [ ] **Identify all `stream()` calls** in your codebase
- [ ] **Add `try-except StreamingError`** around each streaming block
- [ ] **Add `except APIError`** and `RateLimitError` for robustness
- [ ] **Handle empty streams** explicitly (decide: retry, log, raise, etc.)
- [ ] **Test rate limit scenarios** if your app is high-volume
- [ ] **Update error logging/monitoring** to capture new exception types
- [ ] **Review timeout handling** (default 300s - adjust if needed)
- [ ] **Test with both OpenAI and Gemini** providers if you support both

## Backwards Compatibility Matrix

| Feature | v3.2.x | v3.3.0+ | Migration Required? |
|---------|--------|---------|---------------------|
| Basic streaming | ✅ | ✅ | **No** (unless empty stream) |
| File uploads | ✅ | ✅ | No |
| Empty stream handling | Silent fail | Raises error | **YES** |
| Rate limit detection | Silent/broken | Raises `APIError` | **YES** |
| API errors in stream | Ignored | Raises `APIError` | **YES** |
| `on_chunk` callback | ✅ | ✅ | No |
| Timeout support | ✅ (3.2.1+) | ✅ | No |
| Sample chunks in errors | ❌ | ✅ | N/A (new feature) |

## Common Patterns by Use Case

### Web API Endpoint (Flask/FastAPI)

```python
from flask import Flask, Response
from msgmodel import stream, StreamingError, APIError, RateLimitError

@app.route('/stream', methods=['POST'])
def stream_response():
    prompt = request.json.get('prompt')
    
    def generate():
        try:
            for chunk in stream("openai", prompt):
                yield chunk
        except RateLimitError:
            yield "[ERROR: Rate limited, please retry]"
        except StreamingError as e:
            yield f"[ERROR: {e.message}]"
    
    return Response(generate(), mimetype='text/event-stream')
```

### CLI Tool

```python
def main():
    from msgmodel import stream, StreamingError, APIError
    
    prompt = "Your prompt here"
    try:
        for chunk in stream("openai", prompt):
            print(chunk, end="", flush=True)
        print()  # Newline after stream
    except StreamingError as e:
        print(f"\nStream error: {e.message}", file=sys.stderr)
        sys.exit(1)
    except APIError as e:
        print(f"\nAPI error: {e.message}", file=sys.stderr)
        sys.exit(1)
```

### Batch Processing

```python
from msgmodel import stream, APIError, RateLimitError
import time

def process_prompts(prompts):
    for prompt in prompts:
        retry_count = 0
        while retry_count < 3:
            try:
                response = ""
                for chunk in stream("openai", prompt):
                    response += chunk
                print(f"✓ {prompt[:50]}")
                break
            except RateLimitError as e:
                retry_count += 1
                wait = e.retry_after or (2 ** retry_count)
                print(f"⏸ Rate limited. Waiting {wait}s...")
                time.sleep(wait)
            except APIError as e:
                print(f"✗ API error: {e.message}")
                break
```

## Testing Your Migration

```python
import pytest
from msgmodel import stream, StreamingError, APIError

def test_streaming_error_on_empty():
    """Verify StreamingError is raised for empty responses."""
    # This test should PASS on v3.3.0
    with pytest.raises(StreamingError):
        for _ in stream("openai", ""):  # Will fail if API returns no chunks
            pass

def test_handles_rate_limit():
    """Verify rate limit errors are properly caught."""
    from msgmodel import RateLimitError
    try:
        # Simulate rate limit (depends on your test setup)
        for _ in stream("openai", "prompt"):
            pass
    except RateLimitError as e:
        assert e.status_code == 429
```

## FAQ

**Q: My code was working fine before. Why should I upgrade?**
A: v3.3.0 fixes silent failures that could corrupt data or cause confusing behavior. Better to fail loudly than fail silently.

**Q: Do I have to upgrade?**
A: No, but v3.2.x won't receive new features or bug fixes. v3.3.0+ is recommended.

**Q: How do I know if my code needs updating?**
A: If you use the `stream()` function, you should add error handling. If you only use `query()`, no changes needed.

**Q: What about non-streaming `query()` calls?**
A: No changes. `query()` already raised exceptions properly.

**Q: Can I detect provider-specific errors?**
A: Yes! Check `e.provider` in `APIError`: `"openai"` or `"gemini"`

**Q: What's the default timeout for streaming?**
A: 300 seconds (5 minutes). Override with `timeout` parameter in `stream()`

## Support Resources

- **Breaking Changes Details**: See `IMPLEMENTATION_COMPLETE_v3.2.1.md`
- **Exception Reference**: `msgmodel/exceptions.py` - full exception hierarchy
- **Example Code**: See `examples/` directory in msgmodel repo
- **Tests**: `tests/test_v3_2_1_features.py` shows error handling patterns

---

**Release Date**: December 19, 2025  
**Version**: msgmodel 3.3.0  
**Priority**: High - Breaking change affecting streaming code
