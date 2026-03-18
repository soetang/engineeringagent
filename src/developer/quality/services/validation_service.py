from typing import Any, Dict, Optional

import yaml
from pydantic import ValidationError

from developer.config.service import ConfigService

from ..adapters import get_adapters
from ..models import create_dynamic_quality_spec
from .check_collection_service import CheckCollectionService


class ValidationService:
    """Service for validating quality check configuration files."""

    @staticmethod
    def _strip_internal_fields(check_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of check spec without internal metadata fields."""
        return {k: v for k, v in check_spec.items() if not k.startswith("_")}

    def _validate_file_reference(self, check_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a file reference check and return the validated spec entry."""
        if check_spec.get("_missing_file"):
            raise ValueError(
                f"Referenced file not found: {check_spec.get('_error_message', 'unknown file')}"
            )

        resolved_filepath = check_spec.get("_resolved_filepath")
        if resolved_filepath is None:
            raise ValueError("File reference missing resolved filepath")

        # Validate the referenced file content
        self._validate_referenced_file(resolved_filepath)

        return {
            "name": check_spec.get("name", "unnamed"),
            "filepath": resolved_filepath,
            "valid": True,
        }

    def _validate_direct_check(self, check_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a direct check and return the validated spec entry."""
        check_type = check_spec.get("check_type")
        source_file = check_spec.get("_source_file", "unknown")

        if check_type and check_type not in self.supported_check_types:
            raise ValueError(
                f"Unsupported check_type '{check_type}' in {source_file}. "
                f"Supported types: {sorted(self.supported_check_types)}"
            )

        clean_check_spec = self._strip_internal_fields(check_spec)
        # Create a minimal spec with just this check for validation
        minimal_spec = {
            "name": "validation",
            "filepath": source_file,
            "checks": [clean_check_spec],
        }
        # Validate using dynamic model
        self.DynamicQualitySpec(**minimal_spec)

        return {
            "name": check_spec.get("name", check_spec.get("check_type", "unnamed")),
            "filepath": source_file,
            "valid": True,
            "direct_check": True,
        }

    def __init__(self, config_service: Optional[ConfigService] = None):
        """Initialize with dynamic quality spec based on available adapters."""
        self.DynamicQualitySpec = create_dynamic_quality_spec()
        self.supported_check_types = {
            adapter["check_type"] for adapter in get_adapters()
        }
        self.check_collection_service = CheckCollectionService(config_service)

    def validate_checks_yaml(self) -> Dict[str, Any]:
        """Validate the main checks.yaml file and all referenced files."""
        try:
            all_checks = self.check_collection_service.collect_all_checks()
        except ValueError as e:
            return {
                "valid": False,
                "message": str(e),
            }

        # Collect all checks from the configuration tree
        validated_specs = []

        try:
            for check_spec in all_checks:
                source_type = check_spec.get("_source_type")

                if source_type == "file_reference":
                    validated_specs.append(self._validate_file_reference(check_spec))
                    continue

                if source_type == "direct_check":
                    validated_specs.append(self._validate_direct_check(check_spec))
                    continue

                raise ValueError(f"Unknown check source type: {source_type}")

            return {
                "valid": True,
                "checks": validated_specs,
                "message": f"All {len(validated_specs)} check configurations are valid",
            }

        except (ValueError, ValidationError) as e:
            return {
                "valid": False,
                "message": str(e),
            }

    def validate_quality_spec(self, spec_content: Dict[str, Any]) -> Dict[str, Any]:
        """Validate a quality specification dictionary."""
        try:
            self.DynamicQualitySpec(**spec_content)
            return {"valid": True, "message": "Quality specification is valid"}
        except (TypeError, ValueError, ValidationError) as e:
            return {
                "valid": False,
                "message": f"Invalid quality specification: {str(e)}",
            }

    def _validate_referenced_file(self, file_path: str) -> None:
        """Validate a single referenced YAML file against dynamic QualitySpec model."""
        try:
            with open(file_path, "r") as f:
                content = yaml.safe_load(f)

            # Try to parse as dynamic QualitySpec directly
            # The dynamic model should handle all valid check types
            self.DynamicQualitySpec(**content)

        except ValidationError as e:
            raise ValueError(f"Invalid format in {file_path}: {str(e)}")
        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing error in {file_path}: {str(e)}")
        except OSError as e:
            raise ValueError(f"Error validating {file_path}: {str(e)}")
