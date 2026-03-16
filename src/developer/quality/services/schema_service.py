from typing import Dict, Any
from ..models import create_dynamic_quality_spec
from ..adapters import get_adapters


def get_schema_service() -> Dict[str, Any]:
    """
    Returns dynamic schemas based on available adapters.

    Returns:
        Dict with structure:
        {
            "quality_spec_schema": {  # Full QualitySpec JSON schema
                "type": "object",
                "properties": {...},
                "definitions": {...}
            },
            "adapter_schemas": {  # Individual adapter schemas
                "command": {...},
                # ... other adapters
            },
            "supported_check_types": ["command", ...]
        }
    """
    # Get dynamic model
    DynamicQualitySpec = create_dynamic_quality_spec()

    # Generate full schema
    quality_spec_schema = DynamicQualitySpec.model_json_schema()

    # Extract individual adapter schemas from $defs (modern JSON Schema)
    adapter_schemas = {}
    if "$defs" in quality_spec_schema:
        for def_name, def_schema in quality_spec_schema["$defs"].items():
            # Filter out non-adapter definitions (like CheckList)
            if def_name.endswith("Check") and not def_name == "CheckList":
                check_type = def_name.replace("Check", "").lower()
                adapter_schemas[check_type] = def_schema

    # Get supported check types from adapters
    supported_check_types = [adapter["check_type"] for adapter in get_adapters()]

    return {
        "quality_spec_schema": quality_spec_schema,
        "adapter_schemas": adapter_schemas,
        "supported_check_types": sorted(supported_check_types),
    }
