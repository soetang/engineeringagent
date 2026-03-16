from typing import Dict, Any
import yaml
import os
from pathlib import Path
from pydantic import ValidationError
from ..models import create_dynamic_quality_spec
from ..adapters import get_adapters


class ValidationService:
    """Service for validating quality check configuration files."""

    def __init__(self):
        """Initialize with dynamic quality spec based on available adapters."""
        self.DynamicQualitySpec = create_dynamic_quality_spec()
        self.supported_check_types = {
            adapter["check_type"] for adapter in get_adapters()
        }

    def validate_checks_yaml(
        self, file_path: str = "harness/checks.yaml"
    ) -> Dict[str, Any]:
        """Validate the main checks.yaml file and all referenced files."""
        try:
            with open(file_path, "r") as f:
                checks_config = yaml.safe_load(f)

            if not checks_config or "checks" not in checks_config:
                raise ValueError(
                    f"Invalid checks.yaml format: missing 'checks' section in {file_path}"
                )

            validated_specs = []

            for check_spec in checks_config["checks"]:
                if not isinstance(check_spec, dict):
                    raise ValueError(f"Each check must be a dictionary in {file_path}")

                # Handle two types of checks:
                # 1. CheckList items (with filepath) - references to other YAML files
                # 2. CheckType items (with check_type) - direct command checks
                if "filepath" in check_spec:
                    # This is a CheckList item - validate the referenced file
                    ref_file_path = check_spec["filepath"]
                    # Handle both relative and absolute paths
                    if os.path.isabs(ref_file_path):
                        full_ref_path = Path(ref_file_path)
                    else:
                        full_ref_path = Path(file_path).parent / ref_file_path

                    if not full_ref_path.exists():
                        raise FileNotFoundError(
                            f"Referenced file not found: {full_ref_path}"
                        )

                    # Validate the referenced file content
                    self._validate_referenced_file(str(full_ref_path))

                    validated_specs.append(
                        {
                            "name": check_spec.get("name", "unnamed"),
                            "filepath": str(full_ref_path),
                            "valid": True,
                        }
                    )
                elif "check_type" in check_spec:
                    # Validate that check_type is supported
                    check_type = check_spec["check_type"]
                    if check_type not in self.supported_check_types:
                        raise ValueError(
                            f"Unsupported check_type '{check_type}' in {file_path}. "
                            f"Supported types: {sorted(self.supported_check_types)}"
                        )

                    # This is a direct CheckType item - validate it directly
                    # Create a minimal QualitySpec wrapper for validation
                    try:
                        # Create a minimal spec with just this check
                        minimal_spec = {
                            "name": "direct_check_validation",
                            "filepath": file_path,
                            "checks": [check_spec],
                        }
                        # Validate using dynamic model
                        self.DynamicQualitySpec(**minimal_spec)

                        validated_specs.append(
                            {
                                "name": check_spec.get(
                                    "name", check_spec.get("check_type", "unnamed")
                                ),
                                "filepath": file_path,  # Use the main file path for direct checks
                                "valid": True,
                                "direct_check": True,  # Mark as direct check
                            }
                        )
                    except Exception as e:
                        raise ValueError(
                            f"Invalid direct check format in {file_path}: {str(e)}"
                        )
                else:
                    raise ValueError(
                        f"Check must have either 'filepath' or 'check_type' in {file_path}"
                    )

            return {
                "valid": True,
                "checks": validated_specs,
                "message": f"All {len(validated_specs)} check configurations are valid",
            }

        except yaml.YAMLError as e:
            return {
                "valid": False,
                "message": f"YAML parsing error in {file_path}: {str(e)}",
            }
        except (ValueError, FileNotFoundError) as e:
            return {"valid": False, "message": str(e)}
        except Exception as e:
            return {
                "valid": False,
                "message": f"Unexpected error validating {file_path}: {str(e)}",
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

    def _normalize_check_content(self, content: dict) -> dict:
        """Normalize check content to validate command checks."""
        if not isinstance(content, dict) or "checks" not in content:
            return content

        normalized_checks = []
        for check in content["checks"]:
            if isinstance(check, dict):
                normalized_check = check.copy()

                # For command checks, validate they have the required fields
                if normalized_check.get("check_type") == "command":
                    # Command checks need a command field
                    if "command" not in normalized_check:
                        raise ValueError(
                            f"Command check is missing 'command' field: {normalized_check}"
                        )
                    # Remove command field for validation since CheckType doesn't allow it
                    command_field = normalized_check.pop("command")
                    # Store it temporarily to validate it's a list
                    if not isinstance(command_field, list):
                        raise ValueError(
                            f"Command field must be a list, got {type(command_field)}"
                        )

                normalized_checks.append(normalized_check)
            else:
                normalized_checks.append(check)

        normalized_content = content.copy()
        normalized_content["checks"] = normalized_checks
        return normalized_content

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
