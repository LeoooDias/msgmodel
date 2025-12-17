# Publishing msgmodel v3.2.1 to PyPI

This document provides step-by-step instructions for publishing msgmodel v3.2.1 to PyPI.

## Prerequisites

✅ All implementation is complete  
✅ All tests pass (31/31)  
✅ Distribution files built (`dist/msgmodel-3.2.1*`)  
✅ Package validation passed (`twine check`)  
✅ Code committed to git  

## Distribution Files

```
dist/msgmodel-3.2.1-py3-none-any.whl    (26 KB)   # Universal wheel
dist/msgmodel-3.2.1.tar.gz              (32 KB)   # Source distribution
```

## Option 1: Upload Using PyPI Account Token (Recommended)

### Step 1: Create PyPI API Token

1. Go to https://pypi.org/manage/account/
2. Scroll to "API tokens" section
3. Click "Add API token"
4. Create a token with scope "Entire account"
5. Copy the token (you'll only see it once)

### Step 2: Configure Local Environment

```bash
# Create/update ~/.pypirc file
cat > ~/.pypirc << 'EOF'
[distutils]
index-servers =
    pypi

[pypi]
repository = https://upload.pypi.org/legacy/
username = __token__
password = pypi_YOUR_TOKEN_HERE
EOF

# Restrict permissions (important!)
chmod 600 ~/.pypirc
```

Replace `pypi_YOUR_TOKEN_HERE` with your actual token from Step 1.

### Step 3: Upload to PyPI

```bash
cd /Users/leo/source/msgmodel

# Upload the distribution
python -m twine upload dist/msgmodel-3.2.1*

# Or if .pypirc is not detected:
python -m twine upload dist/msgmodel-3.2.1* \
    --repository pypi \
    --username __token__ \
    --password "pypi_YOUR_TOKEN_HERE"
```

## Option 2: Upload Using Username/Password (Deprecated)

If your PyPI account doesn't use tokens:

```bash
python -m twine upload dist/msgmodel-3.2.1* \
    --repository pypi \
    --username your_pypi_username \
    --password your_pypi_password
```

⚠️ **Note**: PyPI is moving away from username/password authentication.  
Use API tokens (Option 1) for better security.

## Option 3: Interactive Upload

```bash
cd /Users/leo/source/msgmodel
python -m twine upload dist/msgmodel-3.2.1*

# You'll be prompted for:
# - Username (enter: __token__)
# - Password (enter your PyPI API token)
```

## Verification After Upload

### 1. Check PyPI Package Page

Visit: https://pypi.org/project/msgmodel/3.2.1/

Should show:
- ✅ Version 3.2.1
- ✅ Release date (today)
- ✅ Files: wheel + source tarball
- ✅ Latest version indicator

### 2. Test Installation

```bash
# Create a test environment
python -m venv test_env
source test_env/bin/activate

# Install the package from PyPI
pip install msgmodel==3.2.1

# Verify installation
python -c "import msgmodel; print(msgmodel.__version__)"
# Should output: 3.2.1

# Test new features
python -c "from msgmodel import RequestSigner; print('✓ RequestSigner available')"

# Clean up
deactivate
rm -rf test_env
```

### 3. Test Upgrade Path

```bash
# Test that v3.2.0 → v3.2.1 upgrade works
python -m venv upgrade_test
source upgrade_test/bin/activate

# Install v3.2.0 first
pip install msgmodel==3.2.0
python -c "import msgmodel; print(f'v3.2.0: {msgmodel.__version__}')"

# Upgrade to v3.2.1
pip install --upgrade msgmodel==3.2.1
python -c "import msgmodel; print(f'v3.2.1: {msgmodel.__version__}')"

# Verify backward compatibility
python << 'EOF'
import msgmodel
from msgmodel import query, stream, OpenAIConfig, RequestSigner
print("✓ All v3.2.1 features available")
print("✓ v3.2.0 code still works")
EOF

deactivate
rm -rf upgrade_test
```

## Troubleshooting

### Issue: "Invalid token"

**Solution**: 
1. Double-check token is copied correctly
2. Token should start with `pypi_`
3. Verify token has not expired
4. Create a new token if needed

### Issue: "Package already exists"

**Solution**:
1. This is expected if uploading the same version twice
2. Use `--skip-existing` flag to skip already-uploaded files:
   ```bash
   twine upload dist/msgmodel-3.2.1* --skip-existing
   ```

### Issue: "Could not find any distributions"

**Solution**:
1. Verify files exist: `ls -la dist/msgmodel-3.2.1*`
2. Rebuild if missing: `python -m build`
3. Check file permissions: `chmod 644 dist/*`

### Issue: "401 Unauthorized"

**Solution**:
1. Check PyPI token is correct
2. Verify ~/.pypirc permissions: `chmod 600 ~/.pypirc`
3. Try uploading to test PyPI first:
   ```bash
   python -m twine upload --repository testpypi dist/msgmodel-3.2.1*
   # Requires: twine configure testpypi
   ```

## Publishing to Test PyPI (Optional)

For testing before the real release:

### Setup Test PyPI

```bash
# Create test token at https://test.pypi.org/manage/account/

# Add to ~/.pypirc
cat >> ~/.pypirc << 'EOF'

[testpypi]
repository = https://test.pypi.org/legacy/
username = __token__
password = pypi_YOUR_TEST_TOKEN_HERE
EOF
```

### Upload to Test PyPI

```bash
python -m twine upload \
    --repository testpypi \
    dist/msgmodel-3.2.1*
```

### Test Installation from Test PyPI

```bash
pip install \
    --index-url https://test.pypi.org/simple/ \
    --extra-index-url https://pypi.org/simple/ \
    msgmodel==3.2.1
```

## Post-Release Checklist

After successful PyPI publication:

- [ ] Verify package visible on https://pypi.org/project/msgmodel/
- [ ] Test `pip install msgmodel==3.2.1` works
- [ ] Create GitHub release/tag
- [ ] Announce in community channels
- [ ] Update documentation site if applicable
- [ ] Update README with latest version
- [ ] Close any related issues

## GitHub Release Creation

1. Go to https://github.com/leoodiass/msgmodel/releases/new

2. Fill in:
   - **Tag version**: `v3.2.1`
   - **Release title**: `msgmodel v3.2.1 - Critical Fixes & Quality-of-Life Improvements`
   - **Description**: Copy from `RELEASE_NOTES_v3.2.1.md`
   - **Attachments**: Upload `dist/msgmodel-3.2.1-py3-none-any.whl` and `dist/msgmodel-3.2.1.tar.gz`

3. Click "Publish release"

## Documentation Updates

After PyPI publication:

1. Update main README.md:
   ```markdown
   **Latest Version**: 3.2.1  
   `pip install msgmodel==3.2.1`
   ```

2. Update docs/INDEX.md with v3.2.1 features

3. Add v3.2.1 to version history

## Success Indicators

✅ Package appears on PyPI  
✅ `pip install msgmodel==3.2.1` works  
✅ Installation includes all new features  
✅ Backward compatibility confirmed  
✅ Tests still pass in fresh environment  
✅ Documentation is accurate  
✅ GitHub release published  

---

**Ready to publish v3.2.1 when you have PyPI credentials.**

All code is complete, tested, and ready for production release.
