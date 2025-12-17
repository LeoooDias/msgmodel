#!/usr/bin/env python
"""
Practical example showing how to use file_like parameter with msgmodel 3.1.0

This example demonstrates:
1. Creating files from various sources
2. Using file_like with query()
3. Using file_like with stream()
4. Comparing file_path vs file_like approaches
"""

import io
import sys
from pathlib import Path


def example_1_basic_usage():
    """Example 1: Basic file_like usage with query()"""
    print("\n" + "=" * 70)
    print("EXAMPLE 1: Basic file_like Usage with query()")
    print("=" * 70)
    
    print("""
from msgmodel import query
import io

# Method 1: File from upload (e.g., FastAPI UploadFile)
# file_bytes = await uploaded_file.read()

# Method 2: File from database or API
# file_bytes = get_file_from_database()

# Method 3: Create from binary content
file_bytes = b"PDF content here..."
file_obj = io.BytesIO(file_bytes)

# Use with msgmodel
response = query(
    provider="openai",
    prompt="Analyze this document",
    file_like=file_obj,  # <-- No disk access!
    system_instruction="You are a document analyst"
)

print(response.text)
    """)


def example_2_streaming():
    """Example 2: Using file_like with stream()"""
    print("\n" + "=" * 70)
    print("EXAMPLE 2: Using file_like with stream()")
    print("=" * 70)
    
    print("""
from msgmodel import stream
import io

# Get file from anywhere (doesn't touch disk)
file_obj = io.BytesIO(binary_file_content)

# Stream response as it arrives
for chunk in stream(
    provider="openai",
    prompt="Describe this image",
    file_like=file_obj,
    system_instruction="Provide detailed analysis"
):
    print(chunk, end="", flush=True)
    """)


def example_3_web_upload():
    """Example 3: Web application with file upload"""
    print("\n" + "=" * 70)
    print("EXAMPLE 3: FastAPI Web Application with File Uploads")
    print("=" * 70)
    
    print("""
from fastapi import FastAPI, UploadFile, File
import io
from msgmodel import query

app = FastAPI()

@app.post("/analyze")
async def analyze_document(file: UploadFile = File(...)):
    # Read uploaded file into BytesIO (never touches disk)
    file_bytes = await file.read()
    file_obj = io.BytesIO(file_bytes)
    
    # Process with msgmodel
    response = query(
        provider="openai",
        prompt=f"Analyze this {file.content_type} file",
        file_like=file_obj,  # Privacy-focused!
        system_instruction="Extract key information"
    )
    
    return {"analysis": response.text}
    """)


def example_4_database():
    """Example 4: Processing files from database"""
    print("\n" + "=" * 70)
    print("EXAMPLE 4: Processing Files from Database")
    print("=" * 70)
    
    print("""
from msgmodel import query
import io

def analyze_document_from_db(doc_id):
    # Retrieve from database
    db_record = database.get(doc_id)
    file_bytes = db_record.file_content
    
    # Convert to BytesIO
    file_obj = io.BytesIO(file_bytes)
    
    # Analyze
    response = query(
        provider="gemini",
        prompt="Extract structured data from this document",
        file_like=file_obj
    )
    
    return response.text
    """)


def example_5_reuse():
    """Example 5: Reusing BytesIO objects"""
    print("\n" + "=" * 70)
    print("EXAMPLE 5: Reusing BytesIO Objects")
    print("=" * 70)
    
    print("""
from msgmodel import query, stream
import io

# Create a reusable BytesIO object
file_obj = io.BytesIO(document_bytes)

# Use it multiple times with different prompts
summary = query(
    provider="openai",
    prompt="Summarize this document",
    file_like=file_obj  # Position automatically reset
)

details = query(
    provider="openai",
    prompt="Extract detailed metadata",
    file_like=file_obj  # Position automatically reset
)

# Even works with streaming
for chunk in stream(
    provider="gemini",
    prompt="Analyze sentiment",
    file_like=file_obj  # Position automatically reset
):
    print(chunk, end="", flush=True)
    """)


def example_6_comparison():
    """Example 6: file_path vs file_like comparison"""
    print("\n" + "=" * 70)
    print("EXAMPLE 6: file_path vs file_like Comparison")
    print("=" * 70)
    
    print("""
from msgmodel import query
import io

# ============================================================
# APPROACH 1: Using file_path (disk-based)
# ============================================================
response1 = query(
    provider="openai",
    prompt="Analyze this file",
    file_path="/path/to/file.pdf"  # Must exist on disk
)

# Pros:
#   - Simple for existing files
#   - Works with file system operations
#
# Cons:
#   - Leaves traces on disk
#   - Not suitable for uploaded files
#   - Not suitable for in-memory data


# ============================================================
# APPROACH 2: Using file_like (memory-based)
# ============================================================
file_bytes = get_file_from_anywhere()
file_obj = io.BytesIO(file_bytes)

response2 = query(
    provider="openai",
    prompt="Analyze this file",
    file_like=file_obj  # No disk access required
)

# Pros:
#   - Privacy-focused (no disk traces)
#   - Works with web uploads
#   - Works with API responses
#   - Can reuse multiple times
#   - More efficient for streaming
#
# Cons:
#   - Requires creating BytesIO object
#   - Entire file loaded in memory (OK for most cases)
    """)


def example_7_error_handling():
    """Example 7: Error handling"""
    print("\n" + "=" * 70)
    print("EXAMPLE 7: Error Handling")
    print("=" * 70)
    
    print("""
from msgmodel import query
from msgmodel.exceptions import ConfigurationError, FileError
import io

# Error 1: Cannot use both file_path and file_like
try:
    query(
        "openai",
        "Hello",
        file_path="/path/to/file",
        file_like=io.BytesIO(b"data")  # ERROR!
    )
except ConfigurationError as e:
    print(f"Error: {e}")
    # Output: Cannot specify both file_path and file_like...


# Error 2: Invalid file-like object
class BadFile:
    def read(self):
        raise IOError("Cannot read")
    def seek(self, pos):
        raise OSError("Cannot seek")

try:
    query("openai", "Hello", file_like=BadFile())
except FileError as e:
    print(f"Error: {e}")
    # Output: Failed to read from file-like object...


# Best Practice: Use context managers
with open('/path/to/file', 'rb') as f:
    file_bytes = f.read()  # Only load when needed

file_obj = io.BytesIO(file_bytes)
response = query("openai", "Analyze", file_like=file_obj)
    """)


def main():
    """Run all examples"""
    print("\n")
    print("╔" + "=" * 68 + "╗")
    print("║" + " " * 10 + "MSGMODEL 3.1.0 - FILE_LIKE USAGE EXAMPLES" + " " * 16 + "║")
    print("╚" + "=" * 68 + "╝")
    
    example_1_basic_usage()
    example_2_streaming()
    example_3_web_upload()
    example_4_database()
    example_5_reuse()
    example_6_comparison()
    example_7_error_handling()
    
    print("\n" + "=" * 70)
    print("KEY BENEFITS OF FILE_LIKE")
    print("=" * 70)
    print("""
✓ PRIVACY: No temporary files on disk
✓ SECURITY: No forensic recovery possible
✓ PERFORMANCE: No encode/decode overhead
✓ COMPATIBILITY: Works with any source of binary data
✓ REUSABILITY: Same BytesIO can be used multiple times
✓ MEMORY: Efficient streaming without loading full file

Ready to use in production!
    """)


if __name__ == "__main__":
    main()
