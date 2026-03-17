from typing import Any, Dict, List
from ..models import create_dynamic_quality_spec
from ..adapters import get_adapters


def get_schema_service() -> Dict[str, Any]:
    """Returns dynamic schemas based on available adapters.

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
    adapter_schemas = {
        def_name.replace("Check", "").lower(): def_schema
        for def_name, def_schema in quality_spec_schema.get("$defs", {}).items()
        if def_name.endswith("Check") and def_name != "CheckList"
    }

    # Get supported check types from adapters
    supported_check_types: List[str] = sorted(
        {
            adapter_dict["check_type"]
            for adapter_dict in get_adapters()
            if isinstance(adapter_dict, dict)
            and isinstance(adapter_dict.get("check_type"), str)
            and adapter_dict.get("check_type")
        }
    )

    return {
        "quality_spec_schema": quality_spec_schema,
        "adapter_schemas": adapter_schemas,
        "supported_check_types": supported_check_types,
    }
