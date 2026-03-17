"""Service for collecting all checks from configuration files."""

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml

from developer.config.service import ConfigService
from developer.quality.settings import QualitySettings


class CheckCollectionService:
    """Service for collecting all checks from configuration files."""

    def __init__(self, config_service: Optional[ConfigService] = None):
        """Initialize the check collection service."""
        self.config_service = config_service or ConfigService()

    def get_checks_path(self) -> str:
        """Get the path to the main checks.yaml file from configuration."""
        settings = self.config_service.get_config("quality", QualitySettings)
        return settings.checks_path

    def collect_all_checks(self) -> List[Dict[str, Any]]:
        """Collect all checks from the configuration tree.
        
        Returns:
            List of dictionaries representing both file references and direct checks.
            File references are preserved as single entries with filepath information.
        """
        file_path = self.get_checks_path()
        all_checks = []

        try:
            with open(file_path, "r") as f:
                checks_config = yaml.safe_load(f)

            if not checks_config or "checks" not in checks_config:
                raise ValueError(
                    f"Invalid checks.yaml format: missing 'checks' section in {file_path}"
                )

            # Process each check specification
            for check_spec in checks_config["checks"]:
                if not isinstance(check_spec, dict):
                    raise ValueError(f"Each check must be a dictionary in {file_path}")

                if "filepath" in check_spec:
                    # This is a file reference - preserve it as a single check entry
                    ref_file_path = check_spec["filepath"]
                    # Handle both relative and absolute paths
                    if os.path.isabs(ref_file_path):
                        full_ref_path = Path(ref_file_path)
                    else:
                        full_ref_path = Path(file_path).parent / ref_file_path

                    # Preserve the file reference as a single check entry
                    file_ref_check = check_spec.copy()
                    file_ref_check["_resolved_filepath"] = str(full_ref_path)
                    file_ref_check["_source_type"] = "file_reference"
                    
                    if not full_ref_path.exists():
                        # Mark as missing file for the execution service to handle
                        file_ref_check["_missing_file"] = True
                        file_ref_check["_error_message"] = f"Referenced file not found: {full_ref_path}"
                    
                    all_checks.append(file_ref_check)
                    
                elif "check_type" in check_spec:
                    # This is a direct check - add it to the list
                    direct_check = check_spec.copy()
                    direct_check["_source_file"] = file_path
                    direct_check["_source_type"] = "direct_check"
                    all_checks.append(direct_check)
                else:
                    raise ValueError(
                        f"Check must have either 'filepath' or 'check_type' in {file_path}"
                    )

            return all_checks

        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing error in {file_path}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error collecting checks from {file_path}: {str(e)}")

    def _collect_checks_from_file(self, file_path: str) -> List[Dict[str, Any]]:
        """Collect checks from a single YAML file.
        
        Args:
            file_path: Path to the YAML file containing checks
            
        Returns:
            List of check dictionaries from the file
        """
        try:
            with open(file_path, "r") as f:
                content = yaml.safe_load(f)

            if not content or "checks" not in content:
                return []  # Empty or invalid file

            checks = []
            
            for check_spec in content["checks"]:
                if isinstance(check_spec, dict):
                    check_copy = check_spec.copy()
                    check_copy["_source_file"] = file_path
                    check_copy["_source_type"] = "nested_check"
                    checks.append(check_copy)
                else:
                    raise ValueError(f"Each check must be a dictionary in {file_path}")

            return checks

        except yaml.YAMLError as e:
            raise ValueError(f"YAML parsing error in {file_path}: {str(e)}")
        except Exception as e:
            raise ValueError(f"Error reading checks from {file_path}: {str(e)}")

    def _resolve_file_path(self, base_path: str, ref_path: str) -> Path:
        """Resolve a file path (absolute or relative to base_path)."""
        if os.path.isabs(ref_path):
            return Path(ref_path)
        else:
            return Path(base_path).parent / ref_path