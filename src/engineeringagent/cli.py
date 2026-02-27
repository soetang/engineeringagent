from __future__ import annotations

import importlib.metadata
import json
import shutil
import sys
from pathlib import Path
from types import SimpleNamespace

import typer
from .agents import default_backend_id, list_backends
from . import cli_typer
from .config import (
    resolve_agents_backend_id,
    write_init_backend_config,
    write_init_docs_root_config,
)
from .git import client as git_client
from .init_scaffold import (
    apply_baseline_scaffold,
    DEFAULT_AGENT_MODEL,
    build_agents_merge_followup_spec,
    build_scaffold_agents_markdown,
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
from .terminal import stdout_is_tty
from . import checks as checks_module
from .specs import HarnessCheckPhase

__all__ = ["HarnessCheckPhase"]

_HandlerArgs = SimpleNamespace

_INIT_PACK_DEFAULT = "slim"
_INIT_PACK_CHOICES: tuple[str, ...] = ("slim", "standard")


def normalize_cli_checks_groups(checks: list[str] | None) -> list[str] | None:
    """Normalize and validate optional checks-group selections."""
    if not checks:
        return None
    try:
        return list(checks_module.normalize_groups(checks))
    except ValueError as exc:
        raise ValueError(f"checks config error: {exc}") from exc


def _resolve_init_pack(pack: str | None) -> tuple[str | None, str | None]:
    """Resolve the init pack (slim|standard), prompting only on TTY when omitted."""
    if pack is not None:
        return pack, None

    if not stdout_is_tty(sys.stdout):
        return _INIT_PACK_DEFAULT, None

    prompt = "init pack: choose [slim/standard] (default slim): "
    selected = input(prompt).strip().lower()
    if selected == "":
        return _INIT_PACK_DEFAULT, None
    if selected in _INIT_PACK_CHOICES:
        return selected, None

    return (
        None,
        "init input error: pack must be 'slim' or 'standard'",
    )


def _backend_choice_error(backend_ids: tuple[str, ...]) -> str:
    """Return deterministic backend input error text."""
    return f"init input error: backend must be one of: {', '.join(backend_ids)}"


def _resolve_init_backend(  # noqa: C901
    *,
    project_root: Path,
    backend: str | None,
    force: bool,
) -> tuple[str | None, str | None]:
    """Resolve init backend choice from CLI args/config/prompt defaults."""
    available_backends = tuple(sorted(list_backends()))
    if not available_backends:
        return None, "init backend error: no registered backends"

    if backend is not None:
        if backend in available_backends:
            return backend, None
        return None, _backend_choice_error(available_backends)

    if not force:
        configured_backend = resolve_agents_backend_id(project_root)
        if configured_backend is not None:
            if configured_backend in available_backends:
                return configured_backend, None
            return None, _backend_choice_error(available_backends)

    if len(available_backends) == 1:
        return available_backends[0], None

    default_backend = default_backend_id()
    if not stdout_is_tty(sys.stdout):
        return default_backend, None

    prompt = (
        f"init backend: choose [{'/'.join(available_backends)}] "
        f"(default {default_backend}): "
    )
    try:
        selected = input(prompt).strip()
    except EOFError:
        selected = ""
    if selected == "":
        return default_backend, None
    if selected in available_backends:
        return selected, None
    return None, _backend_choice_error(available_backends)


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


def _resolve_init_docs_dir(
    project_root: Path,
    docs_mode: str | None,
    scaffold_docs_dir: str,
) -> tuple[str | None, str | None]:
    """Resolve the docs target for scaffold output.

    Args:
        project_root: Repository root where init is running.
        docs_mode: Explicit docs conflict choice when docs/ already exists.
        scaffold_docs_dir: Candidate scaffold docs directory for separate mode.

    Returns:
        Tuple of (resolved docs dir, error message).
    """
    normalized_scaffold_docs_dir = scaffold_docs_dir.strip("/")
    docs_exists = (project_root / "docs").is_dir()

    if not normalized_scaffold_docs_dir:
        return None, "init input error: --scaffold-docs-dir cannot be empty"

    if not docs_exists:
        return "docs", None

    selected_mode = docs_mode
    if selected_mode is None:
        prompt = (
            "init conflict: docs/ already exists. Choose docs handling "
            "[reuse/separate]: "
        )
        selected_mode = input(prompt).strip().lower()

    if selected_mode == "reuse":
        return "docs", None
    if selected_mode == "separate":
        if normalized_scaffold_docs_dir == "docs":
            return (
                None,
                "init input error: --scaffold-docs-dir must differ from docs "
                "when using --docs-mode separate",
            )
        return normalized_scaffold_docs_dir, None

    return (
        None,
        "init input error: docs mode must be 'reuse' or 'separate' when docs/ exists",
    )


def _resolve_init_agents_mode(
    project_root: Path,
    agents_mode: str | None,
) -> tuple[str | None, str | None]:
    """Resolve AGENTS.md conflict behavior.

    Args:
        project_root: Repository root where init is running.
        agents_mode: Explicit AGENTS conflict mode when AGENTS.md already exists.

    Returns:
        Tuple of (resolved mode, error message).
    """
    agents_path = project_root / "AGENTS.md"
    if not agents_path.exists():
        return "create", None

    selected_mode = agents_mode
    if selected_mode is None:
        prompt = (
            "init conflict: AGENTS.md already exists. Choose AGENTS handling "
            "[overwrite/preserve/abort]: "
        )
        selected_mode = input(prompt).strip().lower()

    if selected_mode in {"overwrite", "preserve", "abort"}:
        return selected_mode, None

    return (
        None,
        "init input error: AGENTS mode must be 'overwrite', 'preserve', or 'abort' "
        "when AGENTS.md exists",
    )


def _next_agents_backup_path(project_root: Path) -> Path:
    """Select the next available AGENTS backup path."""
    candidate = project_root / "AGENTS.user.md"
    suffix = 1
    while candidate.exists():
        suffix += 1
        candidate = project_root / f"AGENTS.user.{suffix}.md"
    return candidate


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
    output_path = _resolve_optional_path(path=args.output, project_root=project_root)

    rendered = checks_module.render_fitness_catalog(
        project_root,
        manifest_path=manifest_path,
        format=args.output_format,
    )

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(rendered + "\n", encoding="utf-8")
        try:
            shown_path = output_path.relative_to(project_root)
        except ValueError:
            shown_path = output_path
        print(f"checks catalog written: {shown_path}")
        return 0

    print(rendered)
    return 0


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


def cmd_checks_run(args: _HandlerArgs) -> int:
    """Execute repo-owned checks declared in harness/checks.yaml.

    This command is intended for automation surfaces (e.g. pre-commit, CI) that
    want deterministic execution of repo-owned verification without running the
    full feature loop.
    """

    project_root = Path(args.project_root).resolve()
    result = checks_module.run_checks(
        project_root,
        phase=args.phase,
        checks=getattr(args, "checks", None),
        check_id=getattr(args, "check_id", None),
        feature_path=getattr(args, "feature_path", None),
        verbose_output=bool(getattr(args, "verbose_output", False)),
        base=getattr(args, "base", None),
        head=getattr(args, "head", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )

    failed_runtime_message: str | None = None
    failed_check_type = _resolve_failed_check_type(result)
    if not result.ok and failed_check_type is not None:
        check_id = result.failed_check_id or "unknown"
        failed_runtime_message = (
            f"checks failed: type={failed_check_type} check_id={check_id}"
        )

    exit_code = _emit_run_result(result, noun="checks", success_label="ok")
    if failed_runtime_message is not None:
        print(failed_runtime_message)
    return exit_code


def cmd_fitness_run(args: _HandlerArgs) -> int:
    """Run fitness checks via a compatibility command surface."""

    project_root = Path(args.project_root).resolve()
    result = checks_module.run_checks(
        project_root,
        phase=args.phase,
        checks=["fitness"],
        check_id=getattr(args, "check_id", None),
        base=getattr(args, "base", None),
        head=getattr(args, "head", None),
        dry_run=bool(getattr(args, "dry_run", False)),
    )

    output_format = getattr(args, "output_format", "text")
    if output_format == "json":
        payload = {
            "ok": result.ok,
            "dry_run": result.dry_run,
            "failed_check_id": result.failed_check_id,
            "failed_payload": result.failed_payload,
            "output": result.output,
            "prompt_feedback": result.prompt_feedback,
        }
        print(json.dumps(payload, sort_keys=True))
        return 0 if result.ok else 1

    return _emit_run_result(
        result,
        noun="fitness",
        success_label="ok",
        fail_label="failed",
    )


def cmd_init(args: _HandlerArgs) -> int:  # noqa: C901
    """Scaffold baseline harness files for a repository.

    Args:
        args: Parsed CLI arguments for the init subcommand.

    Returns:
        Process exit code where 0 means success.
    """
    request = InitRequest(
        project_root=Path(args.project_root).resolve(),
        force=bool(args.force),
        scaffold_profile=args.scaffold_profile,
        scaffold_docs_dir=args.scaffold_docs_dir,
        pack=getattr(args, "pack", None),
        backend=getattr(args, "backend", None),
        docs_mode=args.docs_mode,
        agents_mode=getattr(args, "agents_mode", None),
        model=getattr(args, "model", DEFAULT_AGENT_MODEL),
        no_precommit_install=bool(getattr(args, "no_precommit_install", False)),
    )
    deps = InitDependencies(
        emit=print,
        resolve_pack=_resolve_init_pack,
        resolve_backend=_resolve_init_backend,
        resolve_docs_dir=_resolve_init_docs_dir,
        resolve_agents_mode=_resolve_init_agents_mode,
        next_agents_backup_path=_next_agents_backup_path,
        apply_baseline_scaffold=apply_baseline_scaffold,
        write_init_docs_root_config=write_init_docs_root_config,
        write_init_backend_config=write_init_backend_config,
        build_scaffold_agents_markdown=build_scaffold_agents_markdown,
        build_agents_merge_followup_spec=build_agents_merge_followup_spec,
        install_precommit_hooks_best_effort=_install_precommit_hooks_best_effort,
    )
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


def _precommit_remediation_commands(*, scaffold_profile: str) -> list[str]:
    """Return deterministic remediation commands for hook installation."""
    commands = ["pre-commit install"]
    if scaffold_profile == "python_uv":
        commands.append("pre-commit install --hook-type commit-msg")
    return commands


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
    """Best-effort install pre-commit hooks when prerequisites are met.

    Notes:
    - Non-fatal: failures emit deterministic warnings but never raise.
    - Non-interactive: stdin is redirected away from TTY.
    """
    if not (project_root / ".git").exists():
        remediation = " && ".join(
            [
                "git init",
                *_precommit_remediation_commands(scaffold_profile=scaffold_profile),
            ]
        )
        print(
            "init hint: skipped pre-commit hook install (no .git directory). "
            f"To enable later: {remediation}"
        )
        return

    if shutil.which("pre-commit") is None:
        remediation = " && ".join(
            _precommit_remediation_commands(scaffold_profile=scaffold_profile)
        )
        print(
            "init hint: skipped pre-commit hook install (pre-commit not found on PATH). "
            f"To enable later: {remediation}"
        )
        return

    hook_types: list[str | None] = [None]
    if scaffold_profile == "python_uv":
        hook_types.append("commit-msg")

    for hook_type in hook_types:
        retry_command = "pre-commit install"
        if hook_type is not None:
            retry_command = f"pre-commit install --hook-type {hook_type}"

        try:
            result = git_client.precommit_install(project_root, hook_type=hook_type)
        except OSError as exc:
            print(
                "init warning: pre-commit hook install failed "
                f"(error={exc.__class__.__name__}). To retry: {retry_command}"
            )
            continue
        if result.returncode == 0:
            continue
        print(
            "init warning: pre-commit hook install failed "
            f"(exit_code={result.returncode}). To retry: {retry_command}"
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
