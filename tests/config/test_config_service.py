"""Tests for ConfigService."""

import tempfile
import os
from typing import Type
from pydantic import BaseModel, Field
from pydantic import ConfigDict
from developer.config.service import ConfigService


class ConfigTestSettings(BaseModel):
    """Test settings model for testing."""

    string_field: str = Field(default="default_string")
    int_field: int = Field(default=42)
    bool_field: bool = Field(default=True)

    model_config = ConfigDict(extra="forbid")


class ConfigAnotherTestSettings(BaseModel):
    """Another test settings model."""

    name: str = Field(default="test")
    value: float = Field(default=3.14)

    model_config = ConfigDict(extra="forbid")


def create_test_toml(content: str) -> str:
    """Create temporary TOML file with given content."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write(content)
        return f.name


def test_config_service_get_config():
    """Test ConfigService.get_config() method."""
    toml_content = """
[test_section]
string_field = "custom_string"
int_field = 100
bool_field = false

[another_section]
name = "custom_name"
value = 2.71
"""

    temp_file = create_test_toml(toml_content)

    try:
        service = ConfigService(temp_file)

        # Test first section
        settings1 = service.get_config("test_section", ConfigTestSettings)
        assert settings1.string_field == "custom_string"
        assert settings1.int_field == 100
        assert settings1.bool_field is False

        # Test second section
        settings2 = service.get_config("another_section", ConfigAnotherTestSettings)
        assert settings2.name == "custom_name"
        assert settings2.value == 2.71

    finally:
        os.unlink(temp_file)


def test_config_service_caching():
    """Test ConfigService caching functionality."""
    toml_content = """
[test_section]
string_field = "test"
"""

    temp_file = create_test_toml(toml_content)

    try:
        service = ConfigService(temp_file)

        # Get config twice
        settings1 = service.get_config("test_section", ConfigTestSettings)
        settings2 = service.get_config("test_section", ConfigTestSettings)

        # Should be the same object (cached)
        assert settings1 is settings2

        # Clear cache
        service.clear_cache()

        # Get config again - should be different object
        settings3 = service.get_config("test_section", ConfigTestSettings)
        assert settings3 is not settings1
        assert settings3.string_field == settings1.string_field

    finally:
        os.unlink(temp_file)


def test_config_service_missing_section():
    """Test ConfigService with missing section."""
    toml_content = """
[existing_section]
string_field = "test"
"""

    temp_file = create_test_toml(toml_content)

    try:
        service = ConfigService(temp_file)

        # Should use default values for missing section
        settings = service.get_config("missing_section", ConfigTestSettings)
        assert settings.string_field == "default_string"
        assert settings.int_field == 42
        assert settings.bool_field is True

    finally:
        os.unlink(temp_file)


def test_config_service_has_section() -> None:
    """ConfigService should report whether a section exists."""
    toml_content = """
[existing_section]
string_field = "test"
"""

    temp_file = create_test_toml(toml_content)

    try:
        service = ConfigService(temp_file)

        assert service.has_section("existing_section") is True
        assert service.has_section("missing_section") is False

    finally:
        os.unlink(temp_file)


def test_config_service_invalid_data():
    """Test ConfigService with invalid data for model."""
    toml_content = """
[test_section]
string_field = "test"
int_field = "not_a_number"  # Invalid type
"""

    temp_file = create_test_toml(toml_content)

    try:
        service = ConfigService(temp_file)

        try:
            service.get_config("test_section", ConfigTestSettings)
            assert False, "Expected pydantic validation error"
        except Exception as e:
            # Should get pydantic validation error
            assert "validation" in str(e).lower() or "int" in str(e).lower()

    finally:
        os.unlink(temp_file)


def test_config_service_default_file():
    """Test ConfigService with default file name."""
    # Create a temporary directory and file
    with tempfile.TemporaryDirectory() as temp_dir:
        default_file = os.path.join(temp_dir, "engineeringagent.toml")

        with open(default_file, "w") as f:
            f.write("""
[test_section]
string_field = "default_test"
""")

        # Change to temp directory
        old_cwd = os.getcwd()
        os.chdir(temp_dir)

        try:
            service = ConfigService()  # Uses default "engineeringagent.toml"
            settings = service.get_config("test_section", ConfigTestSettings)
            assert settings.string_field == "default_test"

        finally:
            os.chdir(old_cwd)
