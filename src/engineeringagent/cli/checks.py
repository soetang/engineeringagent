from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict

from .. import checks as checks_domain
from ..specs import HarnessCheckPhase
from .output import emit_markdown_output, resolve_optional_path

_HandlerArgs = SimpleNamespace
HandlerArgs = _HandlerArgs

_CHECKS_ALL_PHASES_ORDER: tuple[HarnessCheckPhase, ...] = (
    HarnessCheckPhase.ITERATION_END,
    HarnessCheckPhase.FEATURE_DONE,
    HarnessCheckPhase.MANUAL,
)

reviewers_group_selected = checks_domain.reviewers_group_selected


class _ChecksGitRange(BaseModel):
    """Optional git diff range forwarded to the checks runtime."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    base: str | None
    head: str | None


class _ChecksRunInvocation(BaseModel):
    """Resolved checks-run inputs shared across one or more phase executions."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    project_root: Path
    selected_checks: list[str] | None
    check_id: str | None
    feature_path: str | None
    verbose_output: bool
    git_range: _ChecksGitRange
    dry_run: bool


def normalize_cli_checks_groups(checks: list[str] | None) -> list[str] | None:
    """Normalize and validate optional checks-group selections."""
    if not checks:
        return None
    try:
        return list(checks_domain.normalize_groups(checks))
    except ValueError as exc:
        raise ValueError(f"checks config error: {exc}") from exc


def cmd_checks_catalog(args: _HandlerArgs) -> int:
    """Generate the fitness-rule catalog via the checks surface."""
    project_root = Path(args.project_root).resolve()
    output_path = resolve_optional_path(
        path=getattr(args, "output", None),
        project_root=project_root,
    )
    manifest_path = _resolve_manifest_path(args.manifest_path)
    rendered = checks_domain.render_fitness_catalog(
        project_root,
        manifest_path=manifest_path,
        format=args.output_format,
    )

    return emit_markdown_output(
        rendered,
        project_root=project_root,
        output=output_path,
        output_prefix="checks catalog written",
    )


def _resolve_failed_check_type(
    result: checks_domain.ChecksRunResult,
) -> str | None:
    """Resolve failed check type without relying on group metadata."""
    failed_check_id = result.failed_check_id

    if failed_check_id is not None:
        for execution in result.executions:
            if execution.check_id == failed_check_id:
                return execution.check_type
        for decision in result.decisions:
            if decision["check_id"] == failed_check_id:
                return str(decision["check_type"]).strip() or None

    return None


def _checks_run_phases(
    *,
    requested_phase: HarnessCheckPhase,
    all_phases: bool,
) -> tuple[HarnessCheckPhase, ...]:
    """Return the deterministic phase execution list for checks run."""
    return _CHECKS_ALL_PHASES_ORDER if all_phases else (requested_phase,)


def _build_checks_run_invocation(args: _HandlerArgs) -> _ChecksRunInvocation:
    """Resolve checks-run inputs once before phase execution."""
    return _ChecksRunInvocation(
        project_root=Path(args.project_root).resolve(),
        selected_checks=getattr(args, "checks", None),
        check_id=getattr(args, "check_id", None),
        feature_path=getattr(args, "feature_path", None),
        verbose_output=bool(getattr(args, "verbose_output", False)),
        git_range=_ChecksGitRange(
            base=getattr(args, "base", None),
            head=getattr(args, "head", None),
        ),
        dry_run=bool(getattr(args, "dry_run", False)),
    )


def _run_checks_phases(
    *,
    phases: tuple[HarnessCheckPhase, ...],
    invocation: _ChecksRunInvocation,
    all_phases: bool,
) -> tuple[checks_domain.ChecksRunResult, HarnessCheckPhase | None]:
    """Execute checks for selected phases with deterministic first-failure semantics."""

    result: checks_domain.ChecksRunResult | None = None
    failed_phase: HarnessCheckPhase | None = None
    for phase in phases:
        phase_result = checks_domain.run_checks(
            invocation.project_root,
            phase=phase,
            checks=invocation.selected_checks,
            check_id=invocation.check_id,
            feature_path=invocation.feature_path,
            verbose_output=invocation.verbose_output,
            base=invocation.git_range.base,
            head=invocation.git_range.head,
            dry_run=invocation.dry_run,
        )

        if all_phases and phase_result.output:
            print(f"[phase:{phase.value}]")
            print(phase_result.output)
        result = phase_result
        if phase_result.ok:
            continue
        failed_phase = phase if all_phases else None
        break

    assert result is not None
    return result, failed_phase


def _build_checks_failed_runtime_message(
    *,
    result: checks_domain.ChecksRunResult,
    failed_phase: HarnessCheckPhase | None,
) -> str | None:
    """Build a stable runtime failure summary for failed checks execution."""
    if result.ok:
        return None
    failed_check_type = _resolve_failed_check_type(result)
    if failed_check_type is None:
        return None

    failed_check_id = result.failed_check_id or "unknown"
    if failed_phase is not None:
        return (
            "checks failed: "
            f"phase={failed_phase.value} type={failed_check_type} check_id={failed_check_id}"
        )
    return f"checks failed: type={failed_check_type} check_id={failed_check_id}"


def cmd_checks_run(args: _HandlerArgs) -> int:
    """Execute repo-owned checks declared in repository configuration.

    This command is intended for automation surfaces (e.g. pre-commit, CI) that
    want deterministic execution of repo-owned verification without running the
    full feature loop.
    """
    all_phases = bool(getattr(args, "all_phases", False))
    requested_phase = getattr(args, "phase", HarnessCheckPhase.ITERATION_END)
    phases = _checks_run_phases(
        requested_phase=requested_phase,
        all_phases=all_phases,
    )
    invocation = _build_checks_run_invocation(args)

    if (
        reviewers_group_selected(invocation.selected_checks)
        and invocation.feature_path is None
    ):
        print("checks input error: feature_path is required when reviewers checks are selected")
        return 1

    try:
        result, failed_phase = _run_checks_phases(
            phases=phases,
            invocation=invocation,
            all_phases=all_phases,
        )
    except ValueError as exc:
        print(f"checks input error: {exc}")
        return 1

    failed_runtime_message = _build_checks_failed_runtime_message(
        result=result,
        failed_phase=failed_phase,
    )

    if all_phases and result.ok:
        status_label = "dry-run" if result.dry_run else "run"
        print(f"checks {status_label}: ok")
        return 0

    exit_code = _emit_run_result(result, noun="checks", success_label="ok")
    if failed_runtime_message is not None:
        print(failed_runtime_message)
    return exit_code


def _resolve_manifest_path(manifest_path: str | None) -> Path | None:
    """Return optional manifest path from CLI args."""
    if manifest_path is None:
        return None
    return Path(manifest_path)


def _emit_run_result(
    result: checks_domain.ChecksRunResult,
    *,
    noun: str,
    success_label: str,
    fail_label: str | None = None,
) -> int:
    """Emit stable terminal output and return the CLI exit code."""
    if result.output:
        print(result.output)
    if result.ok:
        status_label = "dry-run" if result.dry_run else "run"
        print(f"{noun} {status_label}: {success_label}")
        return 0
    if fail_label is not None:
        print(f"{noun} run: {fail_label}")
    return 1
