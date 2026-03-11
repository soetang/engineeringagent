"""Application service for deterministic checks execution."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.domain.quality import (
    ChecksRunResult,
    HarnessCheckPhase,
    normalize_check_groups,
)
from engineeringagent.ports import (
    ChecksCatalogRepository,
    ChecksRunRequest,
    ChecksRunner,
)


class RunChecksRequest(BaseModel):
    """Typed input for one checks execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    selected_checks: list[str] | None
    check_id: str | None
    feature_path: str | None
    phase: HarnessCheckPhase
    all_phases: bool
    base: str | None
    head: str | None
    verbose_output: bool
    dry_run: bool


class RunChecksResult(BaseModel):
    """Stable application result for one checks execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_results: tuple[
        tuple[HarnessCheckPhase, ChecksRunResult], ...
    ]
    result: ChecksRunResult
    failed_phase: HarnessCheckPhase | None
    failed_runtime_message: str | None


class ChecksService:
    """Owns deterministic planning and execution of declared checks."""

    _ALL_PHASES_ORDER: tuple[HarnessCheckPhase, ...] = (
        HarnessCheckPhase.ITERATION_END,
        HarnessCheckPhase.FEATURE_DONE,
        HarnessCheckPhase.MANUAL,
    )

    def __init__(
        self,
        checks_runner: ChecksRunner,
        checks_catalog_repository: ChecksCatalogRepository,
    ) -> None:
        self._checks_runner = checks_runner
        self._checks_catalog_repository = checks_catalog_repository

    def run(self, request: RunChecksRequest) -> RunChecksResult:
        """Execute checks with deterministic first-failure semantics."""
        if (
            self._checks_runner.reviewers_group_selected(request.selected_checks)
            and request.feature_path is None
        ):
            raise ValueError(
                "feature_path is required when reviewers checks are selected"
            )

        catalog_preflight = self._load_required_catalog(request)
        if catalog_preflight is not None:
            return catalog_preflight

        phases = self._resolve_phases(request)
        phase_results: list[
            tuple[HarnessCheckPhase, ChecksRunResult]
        ] = []
        result: ChecksRunResult | None = None
        failed_phase: HarnessCheckPhase | None = None
        for phase in phases:
            result = self._coerce_result(
                self._checks_runner.run(
                    ChecksRunRequest(
                        project_root=request.project_root,
                        selected_checks=request.selected_checks,
                        check_id=request.check_id,
                        feature_path=request.feature_path,
                        phase=phase,
                        base=request.base,
                        head=request.head,
                        verbose_output=request.verbose_output,
                        dry_run=request.dry_run,
                    )
                )
            )
            phase_results.append((phase, result))
            if result.ok:
                continue
            failed_phase = phase if request.all_phases else None
            break

        assert result is not None
        return RunChecksResult(
            phase_results=tuple(phase_results),
            result=result,
            failed_phase=failed_phase,
            failed_runtime_message=self._build_failed_runtime_message(
                result=result,
                failed_phase=failed_phase,
            ),
        )

    def _load_required_catalog(
        self,
        request: RunChecksRequest,
    ) -> RunChecksResult | None:
        selected_groups = normalize_check_groups(
            request.selected_checks,
            phase=request.phase,
        )
        if not any(group in {"commands", "fitness", "reviewers"} for group in selected_groups):
            return None

        load_result = self._checks_catalog_repository.load(request.project_root)
        if load_result.error is None:
            return None

        failed_result = ChecksRunResult(
            ok=False,
            dry_run=request.dry_run,
            output=load_result.error,
        )
        return RunChecksResult(
            phase_results=(),
            result=failed_result,
            failed_phase=None,
            failed_runtime_message=None,
        )

    def _resolve_phases(
        self,
        request: RunChecksRequest,
    ) -> tuple[HarnessCheckPhase, ...]:
        if request.all_phases:
            return self._ALL_PHASES_ORDER
        return (request.phase,)

    def _build_failed_runtime_message(
        self,
        *,
        result: ChecksRunResult,
        failed_phase: HarnessCheckPhase | None,
    ) -> str | None:
        if result.ok:
            return None
        failed_check_type = self._resolve_failed_check_type(result)
        if failed_check_type is None:
            return None

        failed_check_id = result.failed_check_id or "unknown"
        if failed_phase is not None:
            return (
                "checks failed: "
                f"phase={failed_phase.value} type={failed_check_type} "
                f"check_id={failed_check_id}"
            )
        return f"checks failed: type={failed_check_type} check_id={failed_check_id}"

    def _resolve_failed_check_type(
        self,
        result: ChecksRunResult,
    ) -> str | None:
        failed_check_id = result.failed_check_id

        if failed_check_id is not None:
            for execution in result.executions:
                if execution.check_id == failed_check_id:
                    return execution.check_type
            for decision in result.decisions:
                if decision["check_id"] == failed_check_id:
                    return str(decision["check_type"]).strip() or None

        return None

    def _coerce_result(self, result: object) -> ChecksRunResult:
        if isinstance(result, ChecksRunResult):
            return result
        return ChecksRunResult.model_validate(
            result,
            from_attributes=True,
        )
