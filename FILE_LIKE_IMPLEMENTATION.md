# File-Like Object (io.BytesIO) Support Implementation

## Summary

Successfully added support for in-memory file objects (`io.BytesIO`) to the `query()` and `stream()` functions in msgmodel, while maintaining full backward compatibility with existing `file_path` parameter.

## Changes Made

### 1. Core Module (`msgmodel/core.py`)

#### New Import
- Added `import io` to support `io.BytesIO` type hints

#### New Function: `_prepare_file_like_data()`
Processes BytesIO objects entirely in memory (never touches disk).

```python
def _prepare_file_like_data(
    file_like: io.BytesIO, 
    filename: str = "upload.bin"
) -> Dict[str, Any]
```

**Features:**
- Seeks to position 0 before reading (supports reusable BytesIO objects)
- Returns position to 0 after reading for potential caller reuse
- Automatically detects MIME type from filename
- Defaults to `application/octet-stream` for unknown extensions
- Marks returned data with `"is_file_like": True` flag
- Raises `FileError` for invalid/non-seekable file-like objects

#### Updated `query()` Function
**New Parameter:** `file_like: Optional[io.BytesIO] = None`

**Changes:**
- Added mutual exclusivity check: raises `ConfigurationError` if both `file_path` and `file_like` are provided
- Routes to appropriate file preparation function based on parameter
- Enhanced docstring with examples showing both disk and in-memory file usage

**Example Usage:**
```python
import io
file_bytes = await uploaded_file.read()  # From FastAPI UploadFile
file_obj = io.BytesIO(file_bytes)

response = query(
    "openai",
    "Analyze this file",
    file_like=file_obj,
    system_instruction="You are a document analyst"
)
```

#### Updated `stream()` Function
**New Parameter:** `file_like: Optional[io.BytesIO] = None`

**Changes:**
- Added mutual exclusivity check (same as `query()`)
- Routes to appropriate file preparation function
- Enhanced docstring with streaming examples

**Example Usage:**
```python
import io
file_obj = io.BytesIO(uploaded_file_bytes)

for chunk in stream(
    "openai",
    "Analyze this uploaded file",
    file_like=file_obj,
    system_instruction="Provide detailed analysis"
):
    print(chunk, end="", flush=True)
```

### 2. Test Suite (`tests/test_core.py`)

#### New Test Class: `TestPrepareFileLikeData`
8 comprehensive tests covering:
- `test_bytesio_with_image` - Image data handling
- `test_bytesio_with_pdf` - PDF data handling
- `test_bytesio_with_unknown_extension` - Unknown MIME type defaults
- `test_bytesio_default_filename` - Default filename fallback
- `test_bytesio_position_reset` - Position reset after reading
- `test_bytesio_reuse` - Multiple reads from same object
- `test_invalid_file_like_raises` - Error handling for invalid objects
- `test_non_seekable_file_raises` - Error handling for non-seekable objects

#### New Test Cases in Existing Classes
**TestQueryFunction:**
- `test_file_path_and_file_like_mutually_exclusive` - Mutual exclusivity validation
- `test_file_like_parameter` - Proper file_like parameter handling

**TestStreamFunction:**
- `test_file_path_and_file_like_mutually_exclusive` - Mutual exclusivity validation
- `test_file_like_parameter` - Proper file_like parameter handling

**Test Results:** ✅ All 28 tests passing

## Key Features

### Privacy ✅
- **No disk access**: Files passed as `file_like` never touch the filesystem
- **Memory-only processing**: Complete in-memory handling from upload to API submission
- **No temporary files**: Avoids forensic recovery risks

### Backward Compatibility ✅
- `file_path` parameter works exactly as before
- All existing code continues to function without changes
- No breaking changes to function signatures

### Mutual Exclusivity ✅
```python
# This raises ConfigurationError:
query("openai", "Hello", file_path="/path/to/file", file_like=bytesio_obj)
# Error: "Cannot specify both file_path and file_like..."
```

### Reusability ✅
```python
file_obj = io.BytesIO(data)
# Can call multiple times - position resets after each use
response1 = query("openai", "First prompt", file_like=file_obj)
response2 = query("openai", "Second prompt", file_like=file_obj)  # Works!
```

## Integration with Backend/Frontend

The implementation is ready to integrate with:

1. **Backend**: Can accept multipart form-data uploads and pass as BytesIO to msgmodel
2. **Frontend**: Can send files directly without base64 encoding
3. **Privacy Chain**: Complete no-disk workflow from upload → processing → API submission

## API Examples

### Query with File-Like Object
```python
import io
from msgmodel import query, OpenAIConfig

# Get file from wherever (upload, download, etc.)
file_bytes = b"PDF content here..."
file_obj = io.BytesIO(file_bytes)

response = query(
    provider="openai",
    prompt="Summarize this document",
    file_like=file_obj,
    config=OpenAIConfig(model="gpt-4"),
    system_instruction="You are a document analyst"
)

print(response.text)
```

### Stream with File-Like Object
```python
import io
from msgmodel import stream

uploaded_data = b"Image data here..."
file_obj = io.BytesIO(uploaded_data)

for chunk in stream(
    provider="gemini",
    prompt="Describe this image",
    file_like=file_obj
):
    print(chunk, end="", flush=True)
```

### Disk File (Still Works!)
```python
from msgmodel import query

# Traditional disk-based file still works
response = query(
    provider="openai",
    prompt="Analyze this PDF",
    file_path="/path/to/document.pdf"
)
```

## Error Handling

### Mutual Exclusivity
```python
from msgmodel import query
from msgmodel.exceptions import ConfigurationError

try:
    query("openai", "Hello", file_path="/path", file_like=bytesio_obj)
except ConfigurationError as e:
    print(f"Error: {e}")
    # Output: Error: Cannot specify both file_path and file_like...
```

### Invalid File-Like Objects
```python
from msgmodel import query
from msgmodel.exceptions import FileError

class BadFile:
    def read(self):
        raise IOError("Cannot read")
    def seek(self, pos):
        raise IOError("Cannot seek")

try:
    query("openai", "Hello", file_like=BadFile())
except FileError as e:
    print(f"Error: {e}")
    # Output: Error: Failed to read from file-like object...
```

## Testing Coverage

- ✅ 28/28 tests passing in test_core.py
- ✅ All existing tests pass (backward compatibility verified)
- ✅ New functionality fully tested
- ✅ Error cases covered
- ✅ Edge cases handled (position reset, reuse, etc.)

## Implementation Status

| Feature | Status |
|---------|--------|
| `file_like` parameter addition | ✅ Complete |
| Mutual exclusivity check | ✅ Complete |
| MIME type detection | ✅ Complete |
| Position reset handling | ✅ Complete |
| Error handling | ✅ Complete |
| Docstring updates | ✅ Complete |
| Test coverage | ✅ Complete |
| Backward compatibility | ✅ Verified |

## Next Steps

The implementation is ready for:
1. Backend integration to pass BytesIO objects from uploaded files
2. Frontend integration to send files directly without base64 encoding
3. Provider-specific optimizations (if providers natively support file-like objects)
4. Documentation updates to reflect new capability
