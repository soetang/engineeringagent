import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel

from developer.config.service import ConfigService
from developer.quality.settings import QualitySettings

from ..adapters import get_adapters
from ..protocol import CheckAdapter
from .check_collection_service import CheckCollectionService


class ExecutionService:
    """Service for executing quality checks."""

    def __init__(self, config_service: Optional[ConfigService] = ConfigService()):
        # Build adapter map from get_adapters()
        self.adapters: Dict[str, CheckAdapter] = {}
        for adapter_dict in get_adapters():
            if not isinstance(adapter_dict, dict):
                continue
            check_type = adapter_dict.get("check_type")
            adapter = adapter_dict.get("adapter")
            if isinstance(check_type, str) and isinstance(adapter, CheckAdapter):
                self.adapters[check_type] = adapter
        self.check_collection_service = CheckCollectionService(config_service)

    def _group_checks_by_type(
        self, checks: List[Dict[str, Any]]
    ) -> Dict[str, List[Dict[str, Any]]]:
        """Group checks by their check_type from raw content."""
        checks_by_type = {}
        for check in checks:
            if isinstance(check, dict) and "check_type" in check:
                check_type = check["check_type"]
                if check_type not in checks_by_type:
                    checks_by_type[check_type] = []
                checks_by_type[check_type].append(check)
        return checks_by_type

    def _coerce_checks_for_adapter(
        self, adapter: CheckAdapter, checks: list
    ) -> list[BaseModel]:
        """Convert raw dicts to proper model instances for adapter consumption."""
        check_model_class = adapter.get_check_type()
        processed_checks = []
        for check in checks:
            if isinstance(check, check_model_class):
                processed_checks.append(check)
            elif isinstance(check, dict):
                processed_checks.append(check_model_class(**check))
        return processed_checks

    def _create_error_result(
        self, file_path: str, check_type: str, message: str
    ) -> Dict[str, Any]:
        """Create a standardized error result."""
        return {
            "name": f"{check_type} checks from {file_path}"
            if check_type != "unknown"
            else f"Checks from {file_path}",
            "status": "ERROR",
            "message": message,
            "success": False,
            "filepath": file_path,
            "check_type": check_type,
        }

    def _create_warning_result(self, file_path: str) -> Dict[str, Any]:
        """Create a standardized warning result for empty files."""
        return {
            "name": f"No checks found in {file_path}",
            "status": "WARNING",
            "message": f"File {file_path} contained no executable checks",
            "success": False,
            "filepath": file_path,
            "check_type": "none",
        }

    def execute_checks(self) -> Dict[str, Any]:
        """Execute all checks specified in checks.yaml and referenced files."""
        try:
            # Collect all checks from the configuration tree
            all_checks = self.check_collection_service.collect_all_checks()

            # Execute each check
            all_results = []
            for check_spec in all_checks:
                source_type = check_spec.get("_source_type")

                if source_type == "file_reference":
                    # This is a file reference - execute checks from the referenced file
                    if check_spec.get("_missing_file"):
                        # Handle missing file case
                        all_results.append(
                            {
                                "name": check_spec.get("name", "unnamed"),
                                "filepath": check_spec.get("_resolved_filepath"),
                                "status": "ERROR",
                                "success": False,
                                "message": check_spec.get(
                                    "_error_message", "File not found"
                                ),
                            }
                        )
                    else:
                        resolved_filepath = check_spec.get("_resolved_filepath")
                        if resolved_filepath is None:
                            all_results.append(
                                {
                                    "name": check_spec.get("name", "unnamed"),
                                    "status": "ERROR",
                                    "success": False,
                                    "message": "File reference missing resolved filepath",
                                }
                            )
                        else:
                            try:
                                file_results = self._execute_file_checks(resolved_filepath)
                                all_results.extend(file_results)
                            except Exception as e:
                                all_results.append(
                                    {
                                        "name": check_spec.get("name", "unnamed"),
                                        "filepath": resolved_filepath,
                                        "status": "ERROR",
                                        "success": False,
                                        "message": f"Error processing file {resolved_filepath}: {str(e)}",
                                    }
                                )
                elif source_type == "direct_check":
                    # This is a direct check
                    check_type = check_spec.get("check_type")

                    if check_type not in self.adapters:
                        all_results.append(
                            {
                                "name": check_spec.get(
                                    "name", check_spec.get("check_type", "unnamed")
                                ),
                                "status": "ERROR",
                                "success": False,
                                "message": f"No adapter available for check type: {check_type}",
                                "check_type": check_type,
                            }
                        )
                        continue

                    try:
                        adapter = self.adapters[check_type]
                        # Remove metadata fields before passing to adapter
                        clean_check_spec = {
                            k: v for k, v in check_spec.items() if not k.startswith("_")
                        }
                        # Convert single check to list format expected by adapter
                        check_list = [clean_check_spec]
                        check_results = adapter.run_check(
                            self._coerce_checks_for_adapter(adapter, check_list)
                        )

                        # Convert CheckResult objects to result dictionaries
                        for result in check_results.results:
                            all_results.append(
                                {
                                    "name": result.name,
                                    "status": result.status.value,
                                    "message": result.message,
                                    "success": result.status.value == "passed",
                                    "check_type": check_type,
                                }
                            )

                    except Exception as e:
                        all_results.append(
                            {
                                "name": check_spec.get(
                                    "name", check_spec.get("check_type", "unnamed")
                                ),
                                "status": "ERROR",
                                "success": False,
                                "message": f"Error executing {check_type} check: {str(e)}",
                                "check_type": check_type,
                            }
                        )
                else:
                    all_results.append(
                        {
                            "name": check_spec.get("name", "unnamed"),
                            "status": "ERROR",
                            "success": False,
                            "message": f"Unknown check source type: {source_type}",
                        }
                    )

            # Calculate summary statistics
            total_checks = len(all_results)
            passed_checks = sum(
                1 for result in all_results if result.get("success", False)
            )
            failed_checks = total_checks - passed_checks

            return {
                "success": failed_checks == 0,
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "failed_checks": failed_checks,
                "results": all_results,
                "message": f"Executed {total_checks} checks: {passed_checks} passed, {failed_checks} failed",
            }

        except FileNotFoundError as e:
            # Handle missing file references gracefully
            return {
                "success": False,
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 1,
                "results": [
                    {
                        "name": "Check configuration",
                        "status": "ERROR",
                        "success": False,
                        "message": str(e),
                    }
                ],
                "message": f"Error executing checks: {str(e)}",
            }
        except Exception as e:
            return {"success": False, "message": f"Error executing checks: {str(e)}"}

    def _execute_file_checks(self, file_path: str) -> List[Dict[str, Any]]:
        """Execute checks from a single YAML file."""
        try:
            with open(file_path, "r") as f:
                content = yaml.safe_load(f)

            if not content or "checks" not in content:
                return [self._create_warning_result(file_path)]

            all_results = []

            for check_spec in content["checks"]:
                # Handle both direct checks and file references within the file
                if "filepath" in check_spec:
                    # This is a nested file reference - execute checks from referenced file
                    ref_file_path = check_spec["filepath"]
                    # Handle both relative and absolute paths
                    if os.path.isabs(ref_file_path):
                        full_ref_path = Path(ref_file_path)
                    else:
                        full_ref_path = Path(file_path).parent / ref_file_path

                    if not full_ref_path.exists():
                        all_results.append(
                            {
                                "name": check_spec.get("name", "unnamed"),
                                "filepath": str(full_ref_path),
                                "status": "ERROR",
                                "success": False,
                                "message": f"Referenced file not found: {full_ref_path}",
                            }
                        )
                        continue

                    # Execute checks from the referenced file
                    file_results = self._execute_file_checks(str(full_ref_path))
                    all_results.extend(file_results)
                elif "check_type" in check_spec:
                    # This is a direct check - execute it directly
                    direct_results = self._execute_direct_check(check_spec)
                    all_results.extend(direct_results)

            return (
                all_results if all_results else [self._create_warning_result(file_path)]
            )

        except Exception as e:
            return [
                self._create_error_result(
                    file_path, "unknown", f"Error processing file {file_path}: {str(e)}"
                )
            ]

    def _execute_direct_check(self, check_spec: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Execute a single direct check specification."""
        check_type = check_spec["check_type"]

        if check_type not in self.adapters:
            return [
                {
                    "name": check_spec.get(
                        "name", check_spec.get("check_type", "unnamed")
                    ),
                    "status": "ERROR",
                    "success": False,
                    "message": f"No adapter available for check type: {check_type}",
                    "check_type": check_type,
                }
            ]

        try:
            adapter = self.adapters[check_type]
            # Convert single check to list format expected by adapter
            check_list = [check_spec]
            check_results = adapter.run_check(
                self._coerce_checks_for_adapter(adapter, check_list)
            )

            return [
                {
                    "name": result.name,
                    "status": result.status.value,
                    "message": result.message,
                    "success": result.status.value == "passed",
                    "check_type": check_type,
                    "direct_check": True,  # Mark as direct check
                }
                for result in check_results.results
            ]
        except Exception as e:
            return [
                {
                    "name": check_spec.get(
                        "name", check_spec.get("check_type", "unnamed")
                    ),
                    "status": "ERROR",
                    "success": False,
                    "message": f"Error executing {check_type} check: {str(e)}",
                    "check_type": check_type,
                    "direct_check": True,
                }
            ]

    def execute_single_spec(self, spec_content: Dict[str, Any]) -> Dict[str, Any]:
        """Execute checks from a single quality specification."""
        try:
            # Group checks by their check_type from raw content
            checks_by_type = self._group_checks_by_type(spec_content.get("checks", []))

            all_results = []

            # Execute checks using appropriate adapters
            for check_type, checks in checks_by_type.items():
                if check_type not in self.adapters:
                    all_results.append(
                        {
                            "name": f"Unknown check type: {check_type}",
                            "status": "ERROR",
                            "message": f"No adapter available for check type: {check_type}",
                            "success": False,
                        }
                    )
                    continue

                adapter = self.adapters[check_type]
                check_results = adapter.run_check(
                    self._coerce_checks_for_adapter(adapter, checks)
                )

                all_results.extend(
                    {
                        "name": result.name,
                        "status": result.status.value,
                        "message": result.message,
                        "success": result.status.value == "passed",
                    }
                    for result in check_results.results
                )

            # Calculate summary
            total_checks = len(all_results)
            passed_checks = sum(
                1 for result in all_results if result.get("success", False)
            )
            failed_checks = total_checks - passed_checks

            return {
                "success": failed_checks == 0,
                "total_checks": total_checks,
                "passed_checks": passed_checks,
                "failed_checks": failed_checks,
                "results": all_results,
            }

        except Exception as e:
            return {
                "success": False,
                "message": f"Error executing quality specification: {str(e)}",
            }
