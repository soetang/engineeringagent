"""Application service for deterministic checks execution."""

from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent import checks as checks_domain


class RunChecksRequest(BaseModel):
    """Typed input for one checks execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    selected_checks: list[str] | None
    check_id: str | None
    feature_path: str | None
    phase: checks_domain.HarnessCheckPhase
    all_phases: bool
    base: str | None
    head: str | None
    verbose_output: bool
    dry_run: bool


class RunChecksResult(BaseModel):
    """Stable application result for one checks execution request."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    phase_results: tuple[
        tuple[checks_domain.HarnessCheckPhase, checks_domain.ChecksRunResult], ...
    ]
    result: checks_domain.ChecksRunResult
    failed_phase: checks_domain.HarnessCheckPhase | None
    failed_runtime_message: str | None


class ChecksService:
    """Owns deterministic planning and execution of declared checks."""

    def run(self, request: RunChecksRequest) -> RunChecksResult:
        """Execute one checks request."""
        raise NotImplementedError


class DefaultChecksService(ChecksService):
    """Default checks application service backed by the checks domain surface."""

    _ALL_PHASES_ORDER: tuple[checks_domain.HarnessCheckPhase, ...] = (
        checks_domain.HarnessCheckPhase.ITERATION_END,
        checks_domain.HarnessCheckPhase.FEATURE_DONE,
        checks_domain.HarnessCheckPhase.MANUAL,
    )

    def run(self, request: RunChecksRequest) -> RunChecksResult:
        """Execute checks with deterministic first-failure semantics."""
        if (
            checks_domain.reviewers_group_selected(request.selected_checks)
            and request.feature_path is None
        ):
            raise ValueError(
                "feature_path is required when reviewers checks are selected"
            )

        phases = self._resolve_phases(request)
        phase_results: list[
            tuple[checks_domain.HarnessCheckPhase, checks_domain.ChecksRunResult]
        ] = []
        result: checks_domain.ChecksRunResult | None = None
        failed_phase: checks_domain.HarnessCheckPhase | None = None
        for phase in phases:
            result = checks_domain.run_checks(
                request.project_root,
                phase=phase,
                checks=request.selected_checks,
                check_id=request.check_id,
                feature_path=request.feature_path,
                verbose_output=request.verbose_output,
                base=request.base,
                head=request.head,
                dry_run=request.dry_run,
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

    def _resolve_phases(
        self,
        request: RunChecksRequest,
    ) -> tuple[checks_domain.HarnessCheckPhase, ...]:
        if request.all_phases:
            return self._ALL_PHASES_ORDER
        return (request.phase,)

    def _build_failed_runtime_message(
        self,
        *,
        result: checks_domain.ChecksRunResult,
        failed_phase: checks_domain.HarnessCheckPhase | None,
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
        result: checks_domain.ChecksRunResult,
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
