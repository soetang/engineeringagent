from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel, ConfigDict

from ...application import RunChecksRequest
from ...bootstrap import AppFactory
from ... import checks as checks_domain
from .output import emit_markdown_output, resolve_optional_path

_HandlerArgs = SimpleNamespace
HandlerArgs = _HandlerArgs
HarnessCheckPhase = checks_domain.HarnessCheckPhase

class _ChecksRunArgs(BaseModel):
    """Resolved checks-run inputs shared across one or more phase executions."""

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


def _build_checks_run_args(args: _HandlerArgs) -> _ChecksRunArgs:
    """Resolve checks-run inputs once before phase execution."""
    return _ChecksRunArgs(
        project_root=Path(args.project_root).resolve(),
        selected_checks=getattr(args, "checks", None),
        check_id=getattr(args, "check_id", None),
        feature_path=getattr(args, "feature_path", None),
        phase=getattr(args, "phase", HarnessCheckPhase.ITERATION_END),
        all_phases=bool(getattr(args, "all_phases", False)),
        verbose_output=bool(getattr(args, "verbose_output", False)),
        base=getattr(args, "base", None),
        head=getattr(args, "head", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )


def cmd_checks_run(args: _HandlerArgs) -> int:
    """Execute repo-owned checks declared in repository configuration.

    This command is intended for automation surfaces (e.g. pre-commit, CI) that
    want deterministic execution of repo-owned verification without running the
    full feature loop.
    """
    invocation = _build_checks_run_args(args)
    service = AppFactory(invocation.project_root).build_checks_service()

    try:
        service_result = service.run(
            RunChecksRequest(
                project_root=invocation.project_root,
                selected_checks=invocation.selected_checks,
                check_id=invocation.check_id,
                feature_path=invocation.feature_path,
                phase=invocation.phase,
                all_phases=invocation.all_phases,
                base=invocation.base,
                head=invocation.head,
                verbose_output=invocation.verbose_output,
                dry_run=invocation.dry_run,
            )
        )
    except ValueError as exc:
        print(f"checks input error: {exc}")
        return 1

    if invocation.all_phases:
        _emit_all_phase_outputs(service_result)

    result = service_result.result
    if invocation.all_phases and result.ok:
        status_label = "dry-run" if result.dry_run else "run"
        print(f"checks {status_label}: ok")
        return 0

    exit_code = _emit_run_result(result, noun="checks", success_label="ok")
    if service_result.failed_runtime_message is not None:
        print(service_result.failed_runtime_message)
    return exit_code


def _emit_all_phase_outputs(service_result: object) -> None:
    """Render per-phase output banners for multi-phase checks runs."""
    for phase, result in getattr(service_result, "phase_results"):
        if not result.output:
            continue
        print(f"[phase:{phase.value}]")
        print(result.output)


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
