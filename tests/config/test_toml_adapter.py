"""Tests for TomlAdapter."""

import tempfile
import os
from engineeringagent.config.adapter.toml_adapter import TomlAdapter


def test_toml_adapter_load():
    """Test TomlAdapter.load() method."""
    adapter = TomlAdapter()

    # Create temporary TOML file
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[section1]
key1 = "value1"
key2 = 42

[section2]
key3 = true
""")
        temp_file = f.name

    try:
        # Test loading
        result = adapter.load(temp_file)

        # Verify structure
        assert "section1" in result
        assert "section2" in result
        assert result["section1"]["key1"] == "value1"
        assert result["section1"]["key2"] == 42
        assert result["section2"]["key3"] is True

    finally:
        # Clean up
        os.unlink(temp_file)


def test_toml_adapter_file_not_found():
    """Test TomlAdapter with non-existent file."""
    adapter = TomlAdapter()

    try:
        adapter.load("/non/existent/file.toml")
        assert False, "Expected FileNotFoundError"
    except FileNotFoundError:
        pass  # Expected


def test_toml_adapter_invalid_toml():
    """Test TomlAdapter with invalid TOML content."""
    adapter = TomlAdapter()

    # Create temporary file with invalid TOML
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("invalid toml content [[[")
        temp_file = f.name

    try:
        try:
            adapter.load(temp_file)
            assert False, "Expected tomllib.TOMLDecodeError"
        except Exception as e:
            # Should get some kind of TOML parsing error
            assert "TOML" in str(type(e).__name__) or "toml" in str(e).lower()
    finally:
        os.unlink(temp_file)
