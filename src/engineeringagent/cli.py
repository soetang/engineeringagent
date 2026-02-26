from __future__ import annotations

import importlib.metadata
import json
import re
import shutil
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import typer
from .agents import default_backend_id, list_backends
from .config import resolve_agents_backend_id
from .git import client as git_client
from .init_scaffold import (
    apply_baseline_scaffold,
    BaselineScaffoldOptions,
    DEFAULT_AGENT_MODEL,
    build_agents_merge_followup_spec,
    build_scaffold_agents_markdown,
)
from .loop import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    run_loop_controller,
)
from .progress import handoff as progress_handoff
from .progress import paths as progress_paths
from . import checks as checks_module
from .specs import HarnessCheckPhase

_HandlerArgs = SimpleNamespace

_INIT_PACK_DEFAULT = "slim"
_INIT_PACK_CHOICES: tuple[str, ...] = ("slim", "standard")


def _normalize_cli_checks_groups(checks: list[str] | None) -> list[str] | None:
    """Normalize and validate optional checks-group selections."""
    if not checks:
        return None
    try:
        return list(checks_module.normalize_groups(checks))
    except ValueError as exc:
        raise ValueError(f"checks config error: {exc}") from exc


def _stdout_is_tty() -> bool:
    """Return True when stdout looks like an interactive TTY."""
    isatty = getattr(sys.stdout, "isatty", None)
    if isatty is None:
        return False
    try:
        return bool(isatty())
    except (OSError, ValueError):
        return False


def _resolve_init_pack(pack: str | None) -> tuple[str | None, str | None]:
    """Resolve the init pack (slim|standard), prompting only on TTY when omitted."""
    if pack is not None:
        return pack, None

    if not _stdout_is_tty():
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
    if not _stdout_is_tty():
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


def _write_init_docs_root_config(
    project_root: Path,
    docs_dir: str,
    *,
    force: bool,
) -> tuple[int, int]:
    """Persist docs-root TOML config when init uses separate docs mode.

    Args:
        project_root: Repository root where init is running.
        docs_dir: Resolved scaffold docs directory.
        force: Whether init is allowed to overwrite existing config files.

    Returns:
        Tuple of (created_count, skipped_count).
    """
    if docs_dir == "docs":
        return (0, 0)

    config_path = project_root / "engineeringagent.toml"
    config_content = f'docs-root = "{docs_dir}"\n'
    if config_path.exists() and not force:
        return (0, 1)

    config_path.write_text(config_content, encoding="utf-8")
    return (1, 0)


_TOML_TABLE_HEADER_RE = re.compile(r"^\s*\[([^\]]+)\]\s*$")
_TOML_AGENTS_BACKEND_RE = re.compile(r"^\s*backend\s*=")


def _ensure_trailing_newline(value: str) -> str:
    """Return text with exactly one trailing newline."""
    return value.rstrip("\n") + "\n"


def _upsert_agents_backend_toml(  # noqa: C901
    *,
    content: str,
    backend_id: str,
    force: bool,
) -> tuple[str, bool]:
    """Insert or update `[agents] backend` in TOML content.

    Returns:
        Tuple of (new_content, changed).
    """
    lines = _ensure_trailing_newline(content).splitlines()
    table_ranges: dict[str, tuple[int, int]] = {}
    table_order: list[tuple[str, int]] = []

    for index, line in enumerate(lines):
        match = _TOML_TABLE_HEADER_RE.match(line)
        if match is None:
            continue
        table_order.append((match.group(1).strip(), index))

    for table_index, (table_name, start) in enumerate(table_order):
        if table_index + 1 < len(table_order):
            end = table_order[table_index + 1][1]
        else:
            end = len(lines)
        table_ranges[table_name] = (start, end)

    agents_range = table_ranges.get("agents")
    if agents_range is None:
        rendered = _ensure_trailing_newline(content).rstrip("\n")
        if rendered:
            rendered += "\n\n"
        rendered += f'[agents]\nbackend = "{backend_id}"\n'
        return rendered, True

    agents_start, agents_end = agents_range
    backend_line_index: int | None = None
    for index in range(agents_start + 1, agents_end):
        if _TOML_AGENTS_BACKEND_RE.match(lines[index]):
            backend_line_index = index
            break

    if backend_line_index is not None:
        current_line = lines[backend_line_index].strip()
        desired_line = f'backend = "{backend_id}"'
        if current_line == desired_line:
            return _ensure_trailing_newline("\n".join(lines)), False
        if not force:
            return _ensure_trailing_newline("\n".join(lines)), False
        lines[backend_line_index] = desired_line
        return _ensure_trailing_newline("\n".join(lines)), True

    insertion_index = agents_end
    while (
        insertion_index > agents_start + 1 and lines[insertion_index - 1].strip() == ""
    ):
        insertion_index -= 1
    lines.insert(insertion_index, f'backend = "{backend_id}"')
    return _ensure_trailing_newline("\n".join(lines)), True


def _write_init_backend_config(
    project_root: Path,
    *,
    backend_id: str,
    force: bool,
) -> tuple[int, int]:
    """Persist `[agents] backend = "..."` in engineeringagent.toml."""
    config_path = project_root / "engineeringagent.toml"
    current_content = ""
    if config_path.exists():
        current_content = config_path.read_text(encoding="utf-8")

    rendered, changed = _upsert_agents_backend_toml(
        content=current_content,
        backend_id=backend_id,
        force=force,
    )
    if not changed:
        return (0, 1)

    config_path.write_text(rendered, encoding="utf-8")
    return (1, 0)


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
        legacy_paths = (
            project_root / "harness" / "gates.yaml",
            project_root / "harness" / "reviewers.yaml",
        )
        legacy_present = [path for path in legacy_paths if path.exists()]
        if legacy_present:
            rendered = ", ".join(
                sorted(
                    str(path.relative_to(project_root)).replace("\\", "/")
                    for path in legacy_present
                )
            )
            print(
                "run config error: legacy harness contract file(s) are no longer supported: "
                f"{rendered}. Migrate to harness/checks.yaml and delete legacy files. "
                "Remediation: run `engineeringagent init`."
            )
            return 1
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
    project_root = Path(args.project_root).resolve()

    pack, error = _resolve_init_pack(getattr(args, "pack", None))
    if error is not None or pack is None:
        print(error)
        return 1

    selected_backend, error = _resolve_init_backend(
        project_root=project_root,
        backend=getattr(args, "backend", None),
        force=bool(args.force),
    )
    if error is not None or selected_backend is None:
        print(error)
        return 1

    docs_dir, error = _resolve_init_docs_dir(
        project_root=project_root,
        docs_mode=args.docs_mode,
        scaffold_docs_dir=args.scaffold_docs_dir,
    )
    if error is not None or docs_dir is None:
        print(error)
        return 1

    resolved_agents_mode, error = _resolve_init_agents_mode(
        project_root=project_root,
        agents_mode=getattr(args, "agents_mode", None),
    )
    if error is not None or resolved_agents_mode is None:
        print(error)
        return 1
    if resolved_agents_mode == "abort":
        print("init aborted: kept existing AGENTS.md; no scaffold files changed")
        return 0

    agents_backup_name: str | None = None
    if resolved_agents_mode == "preserve":
        agents_backup_path = _next_agents_backup_path(project_root)
        (project_root / "AGENTS.md").rename(agents_backup_path)
        agents_backup_name = agents_backup_path.name

    created, skipped = apply_baseline_scaffold(
        project_root=project_root,
        options=BaselineScaffoldOptions(
            force=bool(args.force),
            docs_dir=docs_dir,
            profile=args.scaffold_profile,
            pack=pack,
            backend_id=selected_backend,
            agent_model=getattr(args, "model", DEFAULT_AGENT_MODEL),
        ),
    )

    if pack == "standard":
        print(
            "init pack standard: wired a demo failing fitness rule into precommit (expected to fail)"
        )
    config_created, config_skipped = _write_init_docs_root_config(
        project_root,
        docs_dir,
        force=args.force,
    )
    created += config_created
    skipped += config_skipped

    backend_created, backend_skipped = _write_init_backend_config(
        project_root,
        backend_id=selected_backend,
        force=bool(args.force),
    )
    created += backend_created
    skipped += backend_skipped

    if resolved_agents_mode == "overwrite":
        agents_path = project_root / "AGENTS.md"
        agents_path.write_text(build_scaffold_agents_markdown(), encoding="utf-8")

    merge_spec_output = ""
    if resolved_agents_mode == "preserve" and agents_backup_name is not None:
        merge_spec_relative = (
            Path(docs_dir)
            / "spec"
            / "features"
            / "FEAT-900-merge-preserved-agents-guidance.yaml"
        )
        merge_spec_path = project_root / merge_spec_relative
        if not merge_spec_path.exists() or args.force:
            merge_spec_path.parent.mkdir(parents=True, exist_ok=True)
            merge_spec_path.write_text(
                build_agents_merge_followup_spec(agents_backup_name),
                encoding="utf-8",
            )
            created += 1
            merge_spec_output = f" merge_spec={merge_spec_relative}"
        else:
            skipped += 1
            merge_spec_output = f" merge_spec_skipped={merge_spec_relative}"

    if not getattr(args, "no_precommit_install", False):
        _install_precommit_hooks_best_effort(
            project_root=project_root,
            scaffold_profile=args.scaffold_profile,
        )

    agents_mode_output = f" agents_mode={resolved_agents_mode}"
    if agents_backup_name is not None:
        agents_mode_output += f" agents_backup={agents_backup_name}"

    print(
        f"init scaffold complete: docs_dir={docs_dir} "
        f"created={created} skipped={skipped}"
        f" profile={args.scaffold_profile}"
        f" pack={pack}"
        f"{agents_mode_output}{merge_spec_output}"
    )
    return 0


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


def _version_callback(value: bool) -> None:
    """Print package version and exit early when requested."""
    if not value:
        return
    print(importlib.metadata.version("engineeringagent"))
    raise typer.Exit(code=0)


def _project_root_from_typer_context(ctx: typer.Context) -> str:
    """Extract project-root value stored on the Typer root context."""
    root_ctx = ctx.find_root()
    if isinstance(root_ctx.obj, dict):
        return str(root_ctx.obj.get("project_root", "."))
    return "."


def _exit_with_handler_code(
    handler: Callable[[_HandlerArgs], int],
    *,
    ctx: typer.Context,
    **kwargs: object,
) -> None:
    """Run a command handler and exit with its return code."""
    args = _build_handler_args(ctx=ctx, **kwargs)
    raise typer.Exit(code=handler(args))


def _build_handler_args(ctx: typer.Context, **kwargs: object) -> _HandlerArgs:
    """Build command handler args with root project context."""
    return _HandlerArgs(
        project_root=_project_root_from_typer_context(ctx),
        **kwargs,
    )


def _build_typer_checks_app() -> typer.Typer:
    """Build the Typer checks app with nested command routing."""
    check_groups_help = "|".join(checks_module.list_check_groups())
    checks_app = typer.Typer(
        help="run repo-owned checks from harness/checks.yaml",
        add_completion=False,
        no_args_is_help=False,
    )

    @checks_app.command("run", help="run checks declared in harness/checks.yaml")
    def _checks_run(
        ctx: typer.Context,
        checks: list[str] | None = typer.Option(
            None,
            "--checks",
            help=f"repeatable checks group selection: {check_groups_help}",
        ),
        check_id: str | None = typer.Option(
            None,
            "--check-id",
            help="optional check id to run within selected groups",
        ),
        feature_path: str | None = typer.Option(
            None,
            "--feature-path",
            help="feature spec path required when running reviewers checks",
        ),
        phase: HarnessCheckPhase = typer.Option(
            HarnessCheckPhase.ITERATION_END,
            "--phase",
            help="check execution phase to run (iteration_end|feature_done|manual)",
        ),
        base: str | None = typer.Option(
            None,
            "--base",
            help="optional base revision for on_change diff",
        ),
        head: str | None = typer.Option(
            None,
            "--head",
            help="optional head revision for on_change diff",
        ),
        verbose_output: bool = typer.Option(
            False,
            "--verbose-output",
            help="stream full command output in terminal",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="plan checks only (no command or reviewer execution)",
        ),
    ) -> None:
        try:
            normalized_checks = _normalize_cli_checks_groups(checks)
        except ValueError as exc:
            print(str(exc))
            raise typer.Exit(code=1) from exc

        resolved_feature_path: str | None
        if feature_path is None:
            resolved_feature_path = None
        else:
            resolved_feature_path = str(feature_path).strip() or None

        if normalized_checks is not None and "reviewers" in normalized_checks:
            if resolved_feature_path is None:
                print(
                    "checks config error: --feature-path is required when running reviewers. "
                    "Remediation: re-run with --feature-path <path-to-feature-yaml>."
                )
                raise typer.Exit(code=1)

        _exit_with_handler_code(
            cmd_checks_run,
            ctx=ctx,
            checks=normalized_checks,
            check_id=check_id,
            feature_path=resolved_feature_path,
            phase=phase,
            base=base,
            head=head,
            verbose_output=verbose_output,
            dry_run=dry_run,
        )

    @checks_app.command("catalog", help="generate fitness rule catalog")
    def _checks_catalog(
        ctx: typer.Context,
        manifest_path: str | None = typer.Option(
            None,
            "--manifest-path",
            help="optional path to custom fitness rules manifest",
        ),
        output_format: Literal["markdown", "json"] = typer.Option(
            "markdown",
            "--format",
        ),
        output: str | None = typer.Option(
            None,
            "--output",
            help="write catalog output to a file",
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_checks_catalog,
            ctx=ctx,
            manifest_path=manifest_path,
            output_format=output_format,
            output=output,
        )

    return checks_app


def _build_typer_fitness_app() -> typer.Typer:
    """Build a compatibility fitness app."""

    fitness_app = typer.Typer(
        help="run fitness checks",
        add_completion=False,
        no_args_is_help=False,
    )

    @fitness_app.command("run", help="run configured fitness checks")
    def _fitness_run(
        ctx: typer.Context,
        output_format: Literal["json", "text"] = typer.Option(
            "text",
            "--format",
        ),
        phase: HarnessCheckPhase = typer.Option(
            HarnessCheckPhase.ITERATION_END,
            "--phase",
            help="check execution phase to run (iteration_end|feature_done|manual)",
        ),
        check_id: str | None = typer.Option(
            None,
            "--check-id",
            help="optional fitness check id to run",
        ),
        base: str | None = typer.Option(
            None,
            "--base",
            help="optional base revision for on_change diff",
        ),
        head: str | None = typer.Option(
            None,
            "--head",
            help="optional head revision for on_change diff",
        ),
        dry_run: bool = typer.Option(
            False,
            "--dry-run",
            help="plan checks only (no command execution)",
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_fitness_run,
            ctx=ctx,
            output_format=output_format,
            phase=phase,
            check_id=check_id,
            base=base,
            head=head,
            dry_run=dry_run,
        )

    return fitness_app


def _build_typer_progress_app() -> typer.Typer:
    """Build manual progress helper commands."""

    progress_app = typer.Typer(
        help="manual progress artifact helpers",
        add_completion=False,
        no_args_is_help=False,
    )
    handoff_reference = progress_paths.handoff_markdown_template_reference(Path("."))

    @progress_app.command(
        "handoff-append",
        help="append one feature handoff markdown entry from JSON stdin",
    )
    def _progress_handoff_append(
        ctx: typer.Context,
        feature_id: str = typer.Option(
            ...,
            "--feature-id",
            help=f"feature id used for {handoff_reference}",
        ),
        attempt: int = typer.Option(
            ..., "--attempt", min=1, help="iteration attempt number for heading"
        ),
        timestamp: str | None = typer.Option(
            None,
            "--timestamp",
            help="optional ISO-8601 timestamp override (defaults to current UTC)",
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_progress_handoff_append,
            ctx=ctx,
            feature_id=feature_id,
            attempt=attempt,
            timestamp=timestamp,
        )

    @progress_app.command(
        "feature-prune",
        help="delete one feature-scoped progress directory",
    )
    def _progress_feature_prune(
        ctx: typer.Context,
        feature_id: str = typer.Option(
            ..., "--feature-id", help="feature id under progress/features"
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_progress_feature_prune,
            ctx=ctx,
            feature_id=feature_id,
        )

    return progress_app


def build_typer_app() -> typer.Typer:
    """Build the Typer root app with top-level command wiring."""
    app = typer.Typer(
        name="engineeringagent",
        help="A framework for running coding agents as long running tasks - with deterministic feedback loops and agent reviewers",
        add_completion=False,
        no_args_is_help=False,
    )

    @app.callback(invoke_without_command=False)
    def _root_callback(
        ctx: typer.Context,
        project_root: str = typer.Option(".", "--project-root"),
        version: bool = typer.Option(
            False,
            "--version",
            callback=_version_callback,
            is_eager=True,
        ),
    ) -> None:
        _ = version
        ctx.obj = {"project_root": project_root}

    @app.command("validate", help="validate feature specs")
    def _validate_command(
        ctx: typer.Context,
        schema_only: bool = typer.Option(False, "--schema-only"),
    ) -> None:
        _exit_with_handler_code(
            cmd_validate,
            ctx=ctx,
            schema_only=schema_only,
        )

    @app.command(
        "run",
        help="run feature loops from spec file paths",
    )
    def _run_command(
        ctx: typer.Context,
        feature_paths: list[str] = typer.Argument(None, help="feature spec file paths"),
        run_all: bool = typer.Option(
            False,
            "--all",
            help="auto-discover active feature specs under docs/spec/features",
        ),
        dry_run: bool = typer.Option(False, "--dry-run"),
        max_iterations: int = typer.Option(
            50,
            "--max-iterations",
            help="max non-dry iterations across all selected features",
        ),
        allow_dirty: bool = typer.Option(
            False,
            "--allow-dirty",
            help="allow run execution with uncommitted code changes",
        ),
        verbose_output: bool = typer.Option(
            False,
            "--verbose-output",
            help="stream full implement and gate output in terminal",
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_run,
            ctx=ctx,
            feature_paths=list(feature_paths or []),
            run_all=run_all,
            dry_run=dry_run,
            max_iterations=max_iterations,
            allow_dirty=allow_dirty,
            verbose_output=verbose_output,
        )

    app.add_typer(
        _build_typer_checks_app(),
        name="checks",
        help="run repo-owned checks from harness/checks.yaml",
    )
    app.add_typer(
        _build_typer_fitness_app(),
        name="fitness",
        help="run fitness checks",
    )
    app.add_typer(
        _build_typer_progress_app(),
        name="progress",
        help="manual progress artifact helpers",
    )

    @app.command(
        "init",
        help="scaffold baseline harness files (default core profile)",
    )
    def _init_command(
        ctx: typer.Context,
        pack: Literal["slim", "standard"] | None = typer.Argument(
            None,
            help="optional init pack (slim|standard); omit to prompt on TTY",
        ),
        backend: str | None = typer.Option(
            None,
            "--backend",
            help="agent backend id to persist for repo automation",
        ),
        model: str = typer.Option(
            DEFAULT_AGENT_MODEL,
            "--model",
            help="agent model id for backend-contributed scaffold assets",
            show_default=True,
        ),
        force: bool = typer.Option(
            False,
            "--force",
            help="overwrite scaffold-managed files that already exist",
        ),
        scaffold_profile: Literal["core", "python_uv"] = typer.Option(
            "core",
            "--scaffold-profile",
            help=(
                "scaffold profile to apply "
                "(core=language-agnostic default, python_uv=Python/uv bootstrap)"
            ),
        ),
        docs_mode: Literal["reuse", "separate"] | None = typer.Option(
            None,
            "--docs-mode",
            help="docs conflict mode when docs/ already exists",
        ),
        scaffold_docs_dir: str = typer.Option(
            "docs.engineeringagent",
            "--scaffold-docs-dir",
            help="docs directory to scaffold when using docs-mode=separate",
        ),
        no_precommit_install: bool = typer.Option(
            False,
            "--no-precommit-install",
            help="skip best-effort pre-commit hook installation",
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_init,
            ctx=ctx,
            pack=pack,
            backend=backend,
            model=model,
            force=force,
            scaffold_profile=scaffold_profile,
            docs_mode=docs_mode,
            scaffold_docs_dir=scaffold_docs_dir,
            agents_mode=None,
            no_precommit_install=no_precommit_install,
        )

    return app


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments with Typer and exit with command status."""
    app = build_typer_app()
    app(args=argv, prog_name="engineeringagent")


if __name__ == "__main__":
    sys.exit(main())
