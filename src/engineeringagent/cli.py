from __future__ import annotations

import importlib.metadata
import json
import shutil
import sys
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import typer
import yaml
from .agents import default_backend_id, list_backends
from . import cli_typer
from .approach import (
    UnknownApproachIdError,
    format_approach_topic_index,
    load_topic_content,
    render_approach_overview,
)
from .config import (
    resolve_agents_backend_id,
    resolve_agents_codex_profile_in_engineeringagent_toml,
    write_init_backend_config,
    write_init_docs_root_config,
)
from .git import client as git_client
from .init_scaffold import (
    AGENTS_LAUNCHER_CHOICES,
    apply_baseline_scaffold,
    DEFAULT_AGENT_MODEL,
    DEFAULT_AGENTS_LAUNCHER,
    build_agents_merge_followup_spec,
)
from .init_cli_support import (
    InitAgentsLauncherResolverDeps,
    InitBackendResolverDeps,
    InitCodexProfileResolverDeps,
    InitPromptContext,
    install_precommit_hooks_best_effort as _install_precommit_hooks_best_effort_impl,
    next_agents_backup_path,
    resolve_init_agents_launcher,
    resolve_init_agents_mode,
    resolve_init_backend,
    resolve_init_codex_profile_overwrite,
    resolve_init_docs_dir,
    resolve_init_pack,
)
from .init_service import InitDependencies, InitRequest, run_init_command
from .loop import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    run_loop_controller,
)
from .progress import handoff as progress_handoff
from .progress import paths as progress_paths
from .schema_registry import (
    UnknownSchemaIdError,
    list_schema_ids,
    schema_from_registry,
)
from .terminal import stdout_is_tty
from . import checks as checks_module
from .specs import HarnessCheckPhase

__all__ = ["HarnessCheckPhase"]

_HandlerArgs = SimpleNamespace

_SCHEMA_FORMATS: tuple[str, ...] = ("json", "yaml")
_CHECKS_ALL_PHASES_ORDER: tuple[HarnessCheckPhase, ...] = (
    HarnessCheckPhase.ITERATION_END,
    HarnessCheckPhase.FEATURE_DONE,
    HarnessCheckPhase.MANUAL,
)
reviewers_group_selected = checks_module.reviewers_group_selected


def normalize_cli_checks_groups(checks: list[str] | None) -> list[str] | None:
    """Normalize and validate optional checks-group selections."""
    if not checks:
        return None
    try:
        return list(checks_module.normalize_groups(checks))
    except ValueError as exc:
        raise ValueError(f"checks config error: {exc}") from exc

def _resolve_manifest_path(manifest_path: str | None) -> Path | None:
    """Return optional manifest path from CLI args."""
    if manifest_path is None:
        return None
    return Path(manifest_path)


def _resolve_optional_path(
    *,
    path: str | None,
    project_root: Path,
) -> Path | None:
    """Resolve optional path values relative to project root."""
    if path is None:
        return None
    resolved = Path(path)
    if resolved.is_absolute():
        return resolved
    return project_root / resolved


def cmd_validate(args: _HandlerArgs) -> int:
    """Run feature spec validation and print failures.

    Args:
        args: Parsed CLI arguments for the validate subcommand.

    Returns:
        Process exit code where 0 means validation passed.
    """
    project_root = Path(args.project_root).resolve()
    result = checks_module.run_checks(
        project_root,
        phase="manual",
        checks=["validate"],
        schema_only=bool(getattr(args, "schema_only", False)),
    )
    if not result.ok:
        if result.output:
            for line in result.output.splitlines():
                print(line)
        return 1

    print("spec validation: ok")
    return 0


def cmd_schema_list(args: _HandlerArgs) -> int:
    """Print supported schema ids in deterministic order."""
    _ = args
    for schema_id in list_schema_ids():
        print(schema_id)
    return 0


def _emit_markdown_output(
    payload: str,
    *,
    project_root: Path,
    output: str | None,
    output_prefix: str,
) -> int:
    output_path = _resolve_optional_path(path=output, project_root=project_root)
    if output_path is None:
        print(payload)
        return 0

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(payload + "\n", encoding="utf-8")
    try:
        shown_path = output_path.relative_to(project_root)
    except ValueError:
        shown_path = output_path
    print(f"{output_prefix}: {shown_path}")
    return 0


def cmd_approach_overview(args: _HandlerArgs) -> int:
    """Render CLI-native overview text and topic index."""
    project_root = Path(args.project_root).resolve()
    try:
        overview = load_topic_content("overview")
    except UnknownApproachIdError as exc:
        print(f"approach input error: {exc}")
        return 1
    except ValueError as exc:
        print(f"approach content error: {exc}")
        return 1

    rendered = render_approach_overview(overview)
    return _emit_markdown_output(
        rendered,
        project_root=project_root,
        output=getattr(args, "output", None),
        output_prefix="approach overview written",
    )


def cmd_approach_list(args: _HandlerArgs) -> int:
    """Render a deterministic list of approach topic ids with short titles."""
    output = getattr(args, "output", None)
    rendered = format_approach_topic_index()
    if rendered == "":
        rendered = "No approach topics are available."

    return _emit_markdown_output(
        rendered,
        project_root=Path(args.project_root).resolve(),
        output=output,
        output_prefix="approach list written",
    )


def cmd_approach_show(args: _HandlerArgs) -> int:
    """Render one approach topic by canonical id or alias."""
    project_root = Path(args.project_root).resolve()
    topic_id = str(getattr(args, "topic_id", "")).strip()
    if topic_id == "":
        print(
            "approach input error: provide a topic id or use "
            "`engineeringagent approach list`"
        )
        return 1

    try:
        rendered = load_topic_content(topic_id)
    except UnknownApproachIdError as exc:
        print(f"approach input error: {exc}; use `engineeringagent approach list`")
        return 1
    except ValueError as exc:
        print(f"approach content error: {exc}")
        return 1

    return _emit_markdown_output(
        rendered,
        project_root=project_root,
        output=getattr(args, "output", None),
        output_prefix="approach topic written",
    )


def cmd_schema(args: _HandlerArgs) -> int:
    """Emit one schema from the model-owned registry."""
    raw_schema_id = getattr(args, "schema_id", None)
    schema_id = "" if raw_schema_id is None else str(raw_schema_id).strip()
    if schema_id == "":
        print(
            "schema input error: provide a schema id or use "
            "`engineeringagent schema list`"
        )
        return 1

    raw_format = getattr(args, "output_format", "json")
    output_format = str(raw_format).strip().lower()
    if output_format not in _SCHEMA_FORMATS:
        print("schema input error: --format must be one of: json, yaml")
        return 1

    try:
        schema = schema_from_registry(schema_id)
    except UnknownSchemaIdError as exc:
        print(f"schema input error: {exc}")
        return 1

    if output_format == "json":
        rendered = json.dumps(schema, indent=2, sort_keys=True)
    else:
        rendered = yaml.safe_dump(
            schema,
            sort_keys=True,
            allow_unicode=False,
            default_flow_style=False,
        ).rstrip("\n")

    return _emit_markdown_output(
        rendered,
        project_root=Path(args.project_root).resolve(),
        output=getattr(args, "output", None),
        output_prefix="schema written",
    )


def cmd_run(args: _HandlerArgs) -> int:
    """Execute the loop runner for one or more feature files.

    Args:
        args: Parsed CLI arguments for the run subcommand.

    Returns:
        Process exit code from the loop runner.
    """
    if args.run_all and args.feature_paths:
        print("run input error: positional feature paths cannot be used with --all")
        return 1
    if not args.run_all and not args.feature_paths:
        print("run input error: provide one or more feature paths, or use --all")
        return 1

    project_root = Path(args.project_root).resolve()

    if args.run_all:
        _, checks_error = checks_module.load_harness_checks_document(
            project_root,
            error_prefix="run config error",
            missing_context=" (required for --all)",
        )
        if checks_error is not None:
            print(checks_error)
            return 1

    config = build_run_config(
        project_root=project_root,
        feature_paths=args.feature_paths,
        options=RunConfigOptions(
            args.dry_run,
            args.run_all,
            args.max_iterations,
            args.allow_dirty,
            args.verbose_output,
        ),
    )
    loop_run = build_loop_run(config)
    return run_loop_controller(loop_run)


def cmd_checks_catalog(args: _HandlerArgs) -> int:
    """Generate the fitness-rule catalog via the checks surface."""

    project_root = Path(args.project_root).resolve()
    manifest_path = _resolve_manifest_path(args.manifest_path)
    rendered = checks_module.render_fitness_catalog(
        project_root,
        manifest_path=manifest_path,
        format=args.output_format,
    )

    return _emit_markdown_output(
        rendered,
        project_root=project_root,
        output=args.output,
        output_prefix="checks catalog written",
    )


def _emit_run_result(
    result: checks_module.ChecksRunResult,
    *,
    noun: str,
    success_label: str,
    fail_label: str | None = None,
) -> int:
    if result.output:
        print(result.output)
    if result.ok:
        status_label = "dry-run" if result.dry_run else "run"
        print(f"{noun} {status_label}: {success_label}")
        return 0
    if fail_label is not None:
        print(f"{noun} run: {fail_label}")
    return 1


def _resolve_failed_check_type(
    result: checks_module.ChecksRunResult,
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


def _run_checks_phases(
    *,
    project_root: Path,
    phases: tuple[HarnessCheckPhase, ...],
    selected_checks: list[str] | None,
    check_id: str | None,
    feature_path: str | None,
    verbose_output: bool,
    base: str | None,
    head: str | None,
    dry_run: bool,
    all_phases: bool,
) -> tuple[checks_module.ChecksRunResult, HarnessCheckPhase | None]:
    """Execute checks for selected phases with deterministic first-failure semantics."""

    result: checks_module.ChecksRunResult | None = None
    failed_phase: HarnessCheckPhase | None = None
    for phase in phases:
        phase_result = checks_module.run_checks(
            project_root,
            phase=phase,
            checks=selected_checks,
            check_id=check_id,
            feature_path=feature_path,
            verbose_output=verbose_output,
            base=base,
            head=head,
            dry_run=dry_run,
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
    result: checks_module.ChecksRunResult,
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

    project_root = Path(args.project_root).resolve()
    selected_checks = getattr(args, "checks", None)
    check_id = getattr(args, "check_id", None)
    feature_path = getattr(args, "feature_path", None)
    verbose_output = bool(getattr(args, "verbose_output", False))
    base = getattr(args, "base", None)
    head = getattr(args, "head", None)
    dry_run = bool(getattr(args, "dry_run", False))
    if reviewers_group_selected(selected_checks) and feature_path is None:
        print("checks input error: feature_path is required when reviewers checks are selected")
        return 1

    all_phases = bool(getattr(args, "all_phases", False))
    requested_phase = getattr(args, "phase", HarnessCheckPhase.ITERATION_END)
    phases = _checks_run_phases(requested_phase=requested_phase, all_phases=all_phases)

    try:
        result, failed_phase = _run_checks_phases(
            project_root=project_root,
            phases=phases,
            selected_checks=selected_checks,
            check_id=check_id,
            feature_path=feature_path,
            verbose_output=verbose_output,
            base=base,
            head=head,
            dry_run=dry_run,
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


def _build_init_request(args: _HandlerArgs) -> InitRequest:
    """Build an immutable init request from CLI arguments."""

    return InitRequest(
        project_root=Path(args.project_root).resolve(),
        force=bool(args.force),
        scaffold_profile=args.scaffold_profile,
        scaffold_docs_dir=args.scaffold_docs_dir,
        pack=getattr(args, "pack", None),
        backend=getattr(args, "backend", None),
        docs_mode=args.docs_mode,
        agents_mode=getattr(args, "agents_mode", None),
        agents_launcher=getattr(args, "agents_launcher", None),
        model=getattr(args, "model", DEFAULT_AGENT_MODEL),
        no_precommit_install=bool(getattr(args, "no_precommit_install", False)),
    )


def _build_init_dependencies() -> InitDependencies:
    """Assemble dependency implementations for init execution."""
    prompt_context = InitPromptContext(stdout_is_tty_fn=stdout_is_tty)

    return InitDependencies(
        emit=print,
        resolve_pack=partial(resolve_init_pack, stdout_is_tty_fn=stdout_is_tty),
        resolve_backend=partial(
            resolve_init_backend,
            prompt_context=prompt_context,
            deps=InitBackendResolverDeps(
                list_backends_fn=list_backends,
                resolve_agents_backend_id_fn=resolve_agents_backend_id,
                default_backend_id_fn=default_backend_id,
            ),
        ),
        resolve_docs_dir=resolve_init_docs_dir,
        resolve_agents_mode=resolve_init_agents_mode,
        resolve_agents_launcher=partial(
            resolve_init_agents_launcher,
            prompt_context=prompt_context,
            deps=InitAgentsLauncherResolverDeps(
                launcher_choices=AGENTS_LAUNCHER_CHOICES,
                default_launcher=DEFAULT_AGENTS_LAUNCHER,
            ),
        ),
        resolve_codex_profile_overwrite=partial(
            resolve_init_codex_profile_overwrite,
            prompt_context=prompt_context,
            deps=InitCodexProfileResolverDeps(
                resolve_codex_profile_fn=resolve_agents_codex_profile_in_engineeringagent_toml
            ),
        ),
        next_agents_backup_path=next_agents_backup_path,
        apply_baseline_scaffold=apply_baseline_scaffold,
        write_init_docs_root_config=write_init_docs_root_config,
        write_init_backend_config=write_init_backend_config,
        build_agents_merge_followup_spec=build_agents_merge_followup_spec,
        install_precommit_hooks_best_effort=_install_precommit_hooks_best_effort,
    )


def cmd_init(args: _HandlerArgs) -> int:
    """Scaffold baseline harness files for a repository.

    Args:
        args: Parsed CLI arguments for the init subcommand.

    Returns:
        Process exit code where 0 means success.
    """
    request = _build_init_request(args)
    deps = _build_init_dependencies()
    return run_init_command(request, deps)


def cmd_progress_handoff_append(args: _HandlerArgs) -> int:
    """Append one feature handoff markdown entry from JSON stdin payload."""

    project_root = Path(args.project_root).resolve()
    feature_id = _require_feature_id(args)
    if feature_id is None:
        return 1

    payload = _read_json_stdin_payload()

    envelope, used_fallback = progress_handoff.parse_implement_progress_envelope(
        payload
    )
    entry_lines = progress_handoff.render_handoff_markdown_entry(
        attempt=int(args.attempt),
        envelope=envelope,
        timestamp=getattr(args, "timestamp", None),
        used_fallback=used_fallback,
    )
    handoff_path = progress_paths.handoff_markdown_path(project_root, feature_id)
    progress_handoff.append_handoff_markdown_entry(
        handoff_path=handoff_path,
        entry_lines=entry_lines,
    )
    print(
        "progress handoff append: "
        f"path={progress_paths.handoff_markdown_reference(project_root, feature_id)} "
        f"fallback={str(used_fallback).lower()}"
    )
    return 0


def _read_json_stdin_payload() -> object:
    """Return parsed JSON payload from stdin or empty object on failure."""
    raw_stdin = sys.stdin.read().strip()
    if not raw_stdin:
        return {}
    try:
        return json.loads(raw_stdin)
    except json.JSONDecodeError:
        return {}


def cmd_progress_feature_prune(args: _HandlerArgs) -> int:
    """Delete the feature-scoped progress directory for manual cleanup."""

    project_root = Path(args.project_root).resolve()
    feature_id = _require_feature_id(args)
    if feature_id is None:
        return 1

    target_dir = progress_paths.feature_dir_path(project_root, feature_id)
    target_ref = target_dir.relative_to(project_root)
    if not target_dir.exists():
        print(f"progress feature prune: no-op path={target_ref}")
        return 0

    shutil.rmtree(target_dir)
    print(f"progress feature prune: removed path={target_ref}")
    return 0


def _require_feature_id(args: _HandlerArgs) -> str | None:
    """Return normalized feature id or emit deterministic CLI input error."""
    feature_id = str(args.feature_id).strip()
    if feature_id != "":
        return feature_id
    print("progress input error: --feature-id must be non-empty")
    return None


def _install_precommit_hooks_best_effort(
    *,
    project_root: Path,
    scaffold_profile: str,
) -> None:
    """Best-effort install pre-commit hooks when prerequisites are met."""
    _install_precommit_hooks_best_effort_impl(
        project_root=project_root,
        scaffold_profile=scaffold_profile,
        emit=print,
        shutil_module=shutil,
        git_client_module=git_client,
    )


def version_callback(value: bool) -> None:
    """Print package version and exit early when requested."""
    if not value:
        return
    print(importlib.metadata.version("engineeringagent"))
    raise typer.Exit(code=0)


def build_typer_app() -> typer.Typer:
    """Build the Typer root app with top-level command wiring."""
    return cli_typer.build_typer_app(sys.modules[__name__])


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments with Typer and exit with command status."""
    app = build_typer_app()
    app(args=argv, prog_name="engineeringagent")


if __name__ == "__main__":
    sys.exit(main())
