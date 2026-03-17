import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import ValidationError

from developer.config.service import ConfigService
from developer.quality.settings import QualitySettings

from ..adapters import get_adapters
from ..models import create_dynamic_quality_spec
from .check_collection_service import CheckCollectionService


class ValidationService:
    """Service for validating quality check configuration files."""

    def __init__(self, config_service: Optional[ConfigService] = ConfigService()):
        """Initialize with dynamic quality spec based on available adapters."""
        self.DynamicQualitySpec = create_dynamic_quality_spec()
        self.supported_check_types = {
            adapter["check_type"] for adapter in get_adapters()
        }
        self.check_collection_service = CheckCollectionService(config_service)

    def validate_checks_yaml(self) -> Dict[str, Any]:
        """Validate the main checks.yaml file and all referenced files."""
        try:
            # Collect all checks from the configuration tree
            all_checks = self.check_collection_service.collect_all_checks()

            validated_specs = []

            for check_spec in all_checks:
                source_type = check_spec.get("_source_type")

                if source_type == "file_reference":
                    # This is a file reference - validate the referenced file exists
                    if check_spec.get("_missing_file"):
                        raise ValueError(
                            f"Referenced file not found: {check_spec.get('_error_message', 'unknown file')}"
                        )
                    else:
                        resolved_filepath = check_spec.get("_resolved_filepath")
                        if resolved_filepath is None:
                            raise ValueError("File reference missing resolved filepath")
                        else:
                            try:
                                # Validate the referenced file content
                                self._validate_referenced_file(resolved_filepath)

                                validated_specs.append(
                                    {
                                        "name": check_spec.get("name", "unnamed"),
                                        "filepath": resolved_filepath,
                                        "valid": True,
                                    }
                                )
                            except Exception as e:
                                raise ValueError(
                                    f"Invalid file reference '{resolved_filepath}': {str(e)}"
                                )
                elif source_type == "direct_check":
                    # This is a direct check - validate it
                    check_type = check_spec.get("check_type")
                    source_file = check_spec.get("_source_file", "unknown")

                    # Validate that check_type is supported
                    if check_type and check_type not in self.supported_check_types:
                        raise ValueError(
                            f"Unsupported check_type '{check_type}' in {source_file}. "
                            f"Supported types: {sorted(self.supported_check_types)}"
                        )

                    # Validate the check format using dynamic model
                    try:
                        # Remove metadata fields before validation
                        clean_check_spec = {
                            k: v for k, v in check_spec.items() if not k.startswith("_")
                        }
                        # Create a minimal spec with just this check for validation
                        minimal_spec = {
                            "name": "validation",
                            "filepath": source_file,
                            "checks": [clean_check_spec],
                        }
                        # Validate using dynamic model
                        self.DynamicQualitySpec(**minimal_spec)

                        validated_specs.append(
                            {
                                "name": check_spec.get(
                                    "name", check_spec.get("check_type", "unnamed")
                                ),
                                "filepath": source_file,
                                "valid": True,
                                "direct_check": True,
                            }
                        )

                    except Exception as e:
                        raise ValueError(
                            f"Invalid check format in {source_file}: {str(e)}"
                        )
                else:
                    raise ValueError(f"Unknown check source type: {source_type}")

            return {
                "valid": True,
                "checks": validated_specs,
                "message": f"All {len(validated_specs)} check configurations are valid",
            }

        except Exception as e:
            return {
                "valid": False,
                "message": str(e),
            }

    def validate_quality_spec(self, spec_content: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a quality specification dictionary."""
        try:
            self.DynamicQualitySpec(**spec_content)
            return {"valid": True, "message": "Quality specification is valid"}
        except ValidationError as e:
            return {
                "valid": False,
                "message": f"Invalid quality specification: {str(e)}",
            }
        except Exception as e:
            return {
                "valid": False,
                "message": f"Error validating quality specification: {str(e)}",
            }

    def _validate_referenced_file(self, file_path: str) -> bool:
        """Validate a single referenced YAML file against dynamic QualitySpec model."""
        try:
            with open(file_path, "r") as f:
                content = yaml.safe_load(f)

            # Try to parse as dynamic QualitySpec directly
            # The dynamic model should handle all valid check types
            self.DynamicQualitySpec(**content)
            return True

        except ValidationError as e:
            raise ValueError(f"Invalid format in {file_path}: {str(e)}")
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing error in {file_path}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error validating {file_path}: {str(e)}")
