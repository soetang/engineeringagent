"""Helpers for exporting quality configuration schemas."""

from typing import Any

from developer.quality.models import create_dynamic_quality_spec


def get_quality_schema() -> dict[str, Any]:
    """Return the JSON Schema for the supported quality YAML structure."""
    dynamic_quality_spec = create_dynamic_quality_spec()
    return dynamic_quality_spec.model_json_schema()
