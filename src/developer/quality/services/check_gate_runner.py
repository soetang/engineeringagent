import os
from pathlib import Path
from typing import Any, Dict, List, Optional

import yaml
from pydantic import BaseModel

from developer.config.service import ConfigService
from developer.orchestrator.models import GatePhase, GateResult

from ..adapters import get_adapters
from ..protocol import CheckAdapter
from .check_collection_service import CheckCollectionService


class CheckGateRunner:
    """Service for executing quality checks through phase-aware gates."""

    def __init__(self, config_service: Optional[ConfigService] = None):
        """Initialize the runner and adapter map."""
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

    @staticmethod
    def _coerce_phase(raw_phase: Any) -> GatePhase:
        """Coerce a value into the canonical :class:`GatePhase` enum."""
        if isinstance(raw_phase, GatePhase):
            return raw_phase
        return GatePhase(raw_phase)

    def _strip_internal_fields(self, check_spec: Dict[str, Any]) -> Dict[str, Any]:
        """Return a copy of check spec without internal metadata fields."""
        return {k: v for k, v in check_spec.items() if not k.startswith("_")}

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

    def _group_checks_by_type(
        self, checks: list[Dict[str, Any]]
    ) -> Dict[str, list[Dict[str, Any]]]:
        """Group direct check specs by their declared check type."""
        grouped: Dict[str, list[Dict[str, Any]]] = {}
        for check_spec in checks:
            check_type = check_spec.get("check_type")
            if isinstance(check_type, str):
                grouped.setdefault(check_type, []).append(check_spec)
        return grouped

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

    def _extract_check_name(self, check_spec: Dict[str, Any]) -> str:
        """Return a readable check name for repeated error payloads."""
        name = check_spec.get("name")
        if isinstance(name, str):
            return name

        check_type = check_spec.get("check_type")
        if isinstance(check_type, str):
            return check_type

        return "unnamed"

    def _create_direct_check_error(
        self, check_spec: Dict[str, Any], message: str
    ) -> Dict[str, Any]:
        """Build a common direct-check error result."""
        return {
            "name": self._extract_check_name(check_spec),
            "status": "ERROR",
            "success": False,
            "message": message,
            "check_type": check_spec.get("check_type"),
        }

    def _append_error_entry(
        self,
        target: List[Dict[str, Any]],
        *,
        name: str,
        message: str,
        stop_on_first_failure: bool,
        filepath: str | None = None,
    ) -> bool:
        """Add a single normalized error entry and report stop state."""
        error: Dict[str, Any] = {
            "name": name,
            "status": "ERROR",
            "success": False,
            "message": message,
        }
        if filepath is not None:
            error["filepath"] = filepath
        return self._append_results(target, [error], stop_on_first_failure)

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

    def _result_is_failure(self, result: Dict[str, Any]) -> bool:
        """Return true when a result dictionary represents a failure."""
        return not result.get("success", True)

    def _should_stop_on_failure(
        self, results: List[Dict[str, Any]], stop_on_first_failure: bool
    ) -> bool:
        """Return True when a short-circuit should stop execution."""
        if not stop_on_first_failure:
            return False
        return any(self._result_is_failure(result) for result in results)

    def _append_results(
        self,
        target: List[Dict[str, Any]],
        to_append: List[Dict[str, Any]],
        stop_on_first_failure: bool,
    ) -> bool:
        """Add new results and report whether execution should stop."""
        target.extend(to_append)
        return self._should_stop_on_failure(to_append, stop_on_first_failure)

    def _adapt_check_results(
        self,
        check_results: Any,
        check_type: str | None = None,
    ) -> List[Dict[str, Any]]:
        """Convert adapter check results into plain dictionaries."""
        adapted = []
        for result in check_results.results:
            result_dict = {
                "name": result.name,
                "status": result.status.value,
                "message": result.message,
                "success": result.status.value == "passed",
            }
            if check_type is not None:
                result_dict["check_type"] = check_type
            adapted.append(result_dict)
        return adapted

    def _build_result_summary(
        self,
        all_results: List[Dict[str, Any]],
        stop_on_first_failure: bool,
        stopped_early: bool,
        *,
        truncate_results_on_stop: bool = False,
    ) -> Dict[str, Any]:
        """Build a consistent result payload from accumulated results."""
        summary_results = all_results
        if truncate_results_on_stop and stop_on_first_failure and stopped_early:
            summary_results = all_results[:1]

        total_checks = len(summary_results)
        passed_checks = sum(
            1 for result in summary_results if result.get("success", False)
        )
        failed_checks = total_checks - passed_checks

        message = f"Executed {total_checks} checks: {passed_checks} passed, {failed_checks} failed"
        if stop_on_first_failure and stopped_early and failed_checks > 0:
            message = "Stopped after first failure"

        return {
            "success": failed_checks == 0,
            "total_checks": total_checks,
            "passed_checks": passed_checks,
            "failed_checks": failed_checks,
            "results": summary_results,
            "message": message,
        }

    def _is_phase_match(self, check_spec: Dict[str, Any], phase: GatePhase) -> bool:
        """Return whether this check should run for the requested phase."""
        check_phase = check_spec.get("phase", GatePhase.ITERATION_COMPLETE)
        return self._coerce_phase(check_phase) == phase

    def _build_gate_feedback(self, result: Dict[str, Any]) -> str | None:
        """Extract the failed check message for gate feedback."""
        if result.get("success", False):
            return None

        all_results = result.get("results", [])
        failed = [
            item.get("message")
            for item in all_results
            if isinstance(item, dict) and not item.get("success")
        ]

        for message in failed:
            if message:
                return message

        return result.get("message")

    def check(
        self,
        phase: GatePhase,
        stop_on_first_failure: bool = False,
    ) -> GateResult:
        """Run checks for a phase and return a gate-ready result."""
        result = self.run_checks_for_phase(
            phase=phase,
            stop_on_first_failure=stop_on_first_failure,
        )
        return GateResult(
            passed=bool(result.get("success", False)),
            feedback=self._build_gate_feedback(result),
        )

    def run_checks_for_phase(
        self,
        phase: GatePhase = GatePhase.ITERATION_COMPLETE,
        stop_on_first_failure: bool = False,
    ) -> Dict[str, Any]:
        """Execute checks for a selected phase."""
        try:
            # Collect all checks from the configuration tree
            all_checks = self.check_collection_service.collect_all_checks()

            # Execute each check
            all_results: List[Dict[str, Any]] = []
            stopped_early = False

            for check_spec in all_checks:
                source_type = check_spec.get("_source_type")

                if source_type == "file_reference":
                    # This is a file reference - execute checks from the referenced file
                    if check_spec.get("_missing_file"):
                        if self._append_error_entry(
                            all_results,
                            name=self._extract_check_name(check_spec),
                            filepath=check_spec.get("_resolved_filepath"),
                            message=check_spec.get("_error_message", "File not found"),
                            stop_on_first_failure=stop_on_first_failure,
                        ):
                            stopped_early = True
                            break
                        continue

                    resolved_filepath = check_spec.get("_resolved_filepath")
                    if resolved_filepath is None:
                        if self._append_error_entry(
                            all_results,
                            name=self._extract_check_name(check_spec),
                            message="File reference missing resolved filepath",
                            stop_on_first_failure=stop_on_first_failure,
                        ):
                            stopped_early = True
                            break
                        continue

                    try:
                        file_results = self._execute_file_checks(
                            resolved_filepath,
                            phase=phase,
                            stop_on_first_failure=stop_on_first_failure,
                        )
                        if self._append_results(
                            all_results,
                            file_results,
                            stop_on_first_failure,
                        ):
                            stopped_early = True
                            break
                    except Exception as e:
                        if self._append_error_entry(
                            all_results,
                            name=self._extract_check_name(check_spec),
                            filepath=str(resolved_filepath),
                            message=f"Error processing file {resolved_filepath}: {str(e)}",
                            stop_on_first_failure=stop_on_first_failure,
                        ):
                            stopped_early = True
                            break
                    continue

                if source_type == "direct_check":
                    direct_results = self._execute_direct_check(
                        check_spec,
                        phase=phase,
                    )
                    if self._append_results(
                        all_results,
                        direct_results,
                        stop_on_first_failure,
                    ):
                        stopped_early = True
                        break
                    continue

                if self._append_error_entry(
                    all_results,
                    name=self._extract_check_name(check_spec),
                    message=f"Unknown check source type: {source_type}",
                    stop_on_first_failure=stop_on_first_failure,
                ):
                    stopped_early = True
                    break

            return self._build_result_summary(
                all_results,
                stop_on_first_failure=stop_on_first_failure,
                stopped_early=stopped_early,
            )

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
        except ValueError as e:
            return {
                "success": False,
                "total_checks": 0,
                "passed_checks": 0,
                "failed_checks": 1,
                "message": f"Error executing checks: {str(e)}",
            }
        except Exception as e:
            return {"success": False, "message": f"Error executing checks: {str(e)}"}

    def execute_checks(self) -> Dict[str, Any]:
        """Backward-compatible check run for the default phase."""
        return self.run_checks_for_phase(GatePhase.ITERATION_COMPLETE)

    def _execute_file_checks(
        self,
        file_path: str,
        phase: GatePhase = GatePhase.ITERATION_COMPLETE,
        stop_on_first_failure: bool = False,
    ) -> List[Dict[str, Any]]:
        """Execute checks from a single YAML file."""
        try:
            with open(file_path, "r") as f:
                content = yaml.safe_load(f)

            if not content or "checks" not in content:
                return [self._create_warning_result(file_path)]

            all_results = []
            saw_check_specs = False

            for check_spec in content["checks"]:
                # Handle both direct checks and file references within the file
                if "filepath" in check_spec:
                    saw_check_specs = True
                    # This is a nested file reference - execute checks from referenced file
                    ref_file_path = check_spec["filepath"]
                    # Handle both relative and absolute paths
                    if os.path.isabs(ref_file_path):
                        full_ref_path = Path(ref_file_path)
                    else:
                        full_ref_path = Path(file_path).parent / ref_file_path

                    if not full_ref_path.exists():
                        if self._append_error_entry(
                            all_results,
                            name=self._extract_check_name(check_spec),
                            filepath=str(full_ref_path),
                            message=f"Referenced file not found: {full_ref_path}",
                            stop_on_first_failure=stop_on_first_failure,
                        ):
                            break
                        continue

                    # Execute checks from the referenced file
                    file_results = self._execute_file_checks(
                        str(full_ref_path),
                        phase=phase,
                        stop_on_first_failure=stop_on_first_failure,
                    )
                    if self._append_results(
                        all_results,
                        file_results,
                        stop_on_first_failure,
                    ):
                        break
                elif "check_type" in check_spec:
                    saw_check_specs = True
                    # This is a direct check - execute it directly
                    direct_results = self._execute_direct_check(
                        check_spec,
                        phase=phase,
                    )
                    if self._append_results(
                        all_results, direct_results, stop_on_first_failure
                    ):
                        break

            if all_results:
                return all_results

            if saw_check_specs:
                return []

            return [self._create_warning_result(file_path)]

        except Exception as e:
            return [
                self._create_error_result(
                    file_path,
                    "unknown",
                    f"Error processing file {file_path}: {str(e)}",
                )
            ]

    def _execute_direct_check(
        self,
        check_spec: Dict[str, Any],
        phase: GatePhase = GatePhase.ITERATION_COMPLETE,
    ) -> List[Dict[str, Any]]:
        """Execute a single direct check specification."""
        try:
            if not self._is_phase_match(check_spec, phase):
                return []
        except ValueError as e:
            return [
                self._create_direct_check_error(
                    check_spec,
                    f"Invalid check phase: {str(e)}",
                )
            ]

        check_type = check_spec["check_type"]

        if check_type not in self.adapters:
            return [
                self._create_direct_check_error(
                    check_spec,
                    f"No adapter available for check type: {check_type}",
                )
            ]

        try:
            adapter = self.adapters[check_type]
            # Remove metadata fields before passing to adapter
            clean_check_spec = self._strip_internal_fields(check_spec)
            # Convert single check to list format expected by adapter
            check_list = [clean_check_spec]
            check_results = adapter.run_check(
                self._coerce_checks_for_adapter(adapter, check_list)
            )

            return self._adapt_check_results(
                check_results,
                check_type=check_type,
            )

        except Exception as e:
            return [
                self._create_direct_check_error(
                    check_spec,
                    f"Error executing {check_type} check: {str(e)}",
                )
            ]

    def execute_single_spec(
        self,
        spec_content: Dict[str, Any],
        phase: GatePhase = GatePhase.ITERATION_COMPLETE,
        stop_on_first_failure: bool = False,
    ) -> Dict[str, Any]:
        """Execute checks from a single quality specification."""
        try:
            # Validate and filter check specs for the selected phase
            check_specs = [
                check
                for check in spec_content.get("checks", [])
                if isinstance(check, dict) and self._is_phase_match(check, phase=phase)
            ]

            # Group checks by their check_type from raw content
            checks_by_type = self._group_checks_by_type(check_specs)

            all_results = []
            stopped_early = False

            # Execute checks using appropriate adapters
            for check_type, checks in checks_by_type.items():
                if check_type not in self.adapters:
                    if self._append_results(
                        all_results,
                        [
                            {
                                "name": f"Unknown check type: {check_type}",
                                "status": "ERROR",
                                "message": f"No adapter available for check type: {check_type}",
                                "success": False,
                            }
                        ],
                        stop_on_first_failure,
                    ):
                        stopped_early = True
                        break
                    continue

                adapter = self.adapters[check_type]
                check_results = adapter.run_check(
                    self._coerce_checks_for_adapter(adapter, checks)
                )

                converted_results = self._adapt_check_results(check_results)
                if self._append_results(
                    all_results, converted_results, stop_on_first_failure
                ):
                    stopped_early = True
                    break

            # Calculate summary
            return self._build_result_summary(
                all_results,
                stop_on_first_failure=stop_on_first_failure,
                stopped_early=stopped_early,
                truncate_results_on_stop=True,
            )

        except Exception as e:
            return {
                "success": False,
                "message": f"Error executing quality specification: {str(e)}",
            }
