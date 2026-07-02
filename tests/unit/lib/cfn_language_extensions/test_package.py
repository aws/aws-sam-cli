"""
Tests for package structure and basic imports.
"""

import pytest


class TestPackageStructure:
    """Tests to verify the package is properly structured."""

    def test_package_imports(self):
        """Test that the main package can be imported."""
        import samcli.lib.cfn_language_extensions

        assert samcli.lib.cfn_language_extensions is not None

    def test_package_has_version(self):
        """Test that the package has a version string."""
        from samcli.lib.cfn_language_extensions import __version__

        assert __version__ is not None
        assert isinstance(__version__, str)
        assert len(__version__) > 0

    def test_version_format(self):
        """Test that version follows semantic versioning format."""
        from samcli.lib.cfn_language_extensions import __version__

        parts = __version__.split(".")
        assert len(parts) >= 2, "Version should have at least major.minor"
        # Each part should be numeric (possibly with pre-release suffix)
        assert parts[0].isdigit(), "Major version should be numeric"
        assert parts[1].isdigit(), "Minor version should be numeric"
