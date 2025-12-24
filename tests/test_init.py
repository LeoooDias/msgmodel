"""
Tests for msgmodel.__init__ module.

Tests the lazy loading of async functions.
"""

import pytest


class TestLazyImports:
    """Tests for lazy import functionality in __init__.py."""
    
    def test_lazy_import_aquery(self):
        """Test that aquery is lazily imported."""
        import msgmodel
        # Access aquery through __getattr__
        aquery = msgmodel.aquery
        assert callable(aquery)
        assert aquery.__name__ == "aquery"
    
    def test_lazy_import_astream(self):
        """Test that astream is lazily imported."""
        import msgmodel
        # Access astream through __getattr__
        astream = msgmodel.astream
        # astream is a generator function, check it exists
        assert astream is not None
    
    def test_lazy_import_unknown_raises(self):
        """Test that unknown attribute raises AttributeError."""
        import msgmodel
        with pytest.raises(AttributeError, match="has no attribute"):
            _ = msgmodel.nonexistent_function
    
    def test_version_accessible(self):
        """Test that __version__ is accessible."""
        import msgmodel
        import re
        assert hasattr(msgmodel, "__version__")
        assert isinstance(msgmodel.__version__, str)
        # Validate semantic versioning format (e.g., "4.0.1")
        assert re.match(r'^\d+\.\d+\.\d+', msgmodel.__version__)
