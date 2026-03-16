from typing import Any, Dict, List, Type
import yaml
import os
from pathlib import Path
from pydantic import BaseModel
from ..adapters import get_adapters
from ..protocol import CheckAdapter


class ExecutionService:
    """Service for executing quality checks."""

    def __init__(self):
        # Build adapter map from get_adapters()
        self.adapters: Dict[str, CheckAdapter] = {}
        for adapter_dict in get_adapters():
            if isinstance(adapter_dict, dict):
                check_type = adapter_dict.get("check_type")
                adapter = adapter_dict.get("adapter")
                if check_type and adapter:
                    self.adapters[check_type] = adapter  # pyrefly: ignore[unsupported-operation, bad-argument-type]

    def execute_checks(self, file_path: str = "harness/checks.yaml") -> Dict[str, Any]:
        """Execute all checks specified in checks.yaml and referenced files."""
        try:
            # Read and validate the main checks file
            with open(file_path, "r") as f:
                checks_config = yaml.safe_load(f)

            if not checks_config or "checks" not in checks_config:
                return {
                    "success": False,
                    "message": f"Invalid checks.yaml format: missing 'checks' section in {file_path}",
                }

            all_results = []

            for check_spec in checks_config["checks"]:
                if "filepath" not in check_spec:
                    continue

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
                            "success": False,
                            "message": f"Referenced file not found: {full_ref_path}",
                        }
                    )
                    continue

                # Execute checks from the referenced file
                file_results = self._execute_file_checks(str(full_ref_path))
                all_results.extend(file_results)

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

        except yaml.YAMLError as e:
            return {
                "success": False,
                "message": f"YAML parsing error in {file_path}: {str(e)}",
            }
        except Exception as e:
            return {"success": False, "message": f"Error executing checks: {str(e)}"}

    def _execute_file_checks(self, file_path: str) -> List[Dict[str, Any]]:
        """Execute checks from a single YAML file."""
        results = []

        try:
            with open(file_path, "r") as f:
                content = yaml.safe_load(f)

            # Group checks by their check_type from raw content
            checks_by_type = {}
            for check in content.get("checks", []):
                if isinstance(check, dict) and "check_type" in check:
                    check_type = check["check_type"]
                    if check_type not in checks_by_type:
                        checks_by_type[check_type] = []
                    checks_by_type[check_type].append(check)

            # Execute checks using appropriate adapters
            for check_type, checks in checks_by_type.items():
                if check_type in self.adapters:
                    adapter = self.adapters[check_type]
                    try:
                        check_results = adapter.run_check(checks)

                        for result in check_results.results:
                            results.append(
                                {
                                    "name": result.name,
                                    "status": result.status.value,
                                    "message": result.message,
                                    "success": result.status.value == "passed",
                                    "filepath": file_path,
                                    "check_type": check_type,
                                }
                            )
                    except Exception as e:
                        results.append(
                            {
                                "name": f"{check_type} checks from {file_path}",
                                "status": "ERROR",
                                "message": f"Error executing {check_type} checks: {str(e)}",
                                "success": False,
                                "filepath": file_path,
                                "check_type": check_type,
                            }
                        )
                else:
                    results.append(
                        {
                            "name": f"Unknown check type: {check_type}",
                            "status": "ERROR",
                            "message": f"No adapter available for check type: {check_type}",
                            "success": False,
                            "filepath": file_path,
                            "check_type": check_type,
                        }
                    )

        except Exception as e:
            results.append(
                {
                    "name": f"Checks from {file_path}",
                    "status": "ERROR",
                    "message": f"Error processing file {file_path}: {str(e)}",
                    "success": False,
                    "filepath": file_path,
                    "check_type": "unknown",
                }
            )

        return (
            results
            if results
            else [
                {
                    "name": f"No checks found in {file_path}",
                    "status": "WARNING",
                    "message": f"File {file_path} contained no executable checks",
                    "success": False,
                    "filepath": file_path,
                    "check_type": "none",
                }
            ]
        )

    def execute_single_spec(self, spec_content: Dict[str, Any]) -> Dict[str, Any]:
        """Execute checks from a single quality specification."""
        try:
            # Group checks by their check_type from raw content
            checks_by_type = {}
            for check in spec_content.get("checks", []):
                if isinstance(check, dict) and "check_type" in check:
                    check_type = check["check_type"]
                    if check_type not in checks_by_type:
                        checks_by_type[check_type] = []
                    checks_by_type[check_type].append(check)

            all_results = []

            # Execute checks using appropriate adapters
            for check_type, checks in checks_by_type.items():
                if check_type in self.adapters:
                    adapter = self.adapters[check_type]
                    check_results = adapter.run_check(checks)

                    for result in check_results.results:
                        all_results.append(
                            {
                                "name": result.name,
                                "status": result.status.value,
                                "message": result.message,
                                "success": result.status.value == "passed",
                            }
                        )
                else:
                    all_results.append(
                        {
                            "name": f"Unknown check type: {check_type}",
                            "status": "ERROR",
                            "message": f"No adapter available for check type: {check_type}",
                            "success": False,
                        }
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
