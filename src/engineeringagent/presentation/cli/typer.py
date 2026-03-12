from __future__ import annotations

from collections.abc import Callable
from types import ModuleType, SimpleNamespace
from typing import Literal

import click
import typer

from ... import checks as checks_module
from ...bootstrap.init_scaffold import AGENTS_LAUNCHER_CHOICES
from ...ports import DEFAULT_AGENT_MODEL
_HandlerArgs = SimpleNamespace
HarnessCheckPhase = checks_module.HarnessCheckPhase


def project_root_from_typer_context(ctx: typer.Context) -> str:
    """Extract project-root value stored on the Typer root context."""
    root_ctx = ctx.find_root()
    if isinstance(root_ctx.obj, dict):
        return str(root_ctx.obj.get("project_root", "."))
    return "."


def _build_handler_args(ctx: typer.Context, **kwargs: object) -> _HandlerArgs:
    """Build command handler args with root project context."""
    return _HandlerArgs(
        project_root=project_root_from_typer_context(ctx),
        **kwargs,
    )


def _exit_with_handler_code(
    handler: Callable[[_HandlerArgs], int],
    *,
    ctx: typer.Context,
    **kwargs: object,
) -> None:
    """Run a command handler and exit with its return code."""
    args = _build_handler_args(ctx=ctx, **kwargs)
    raise typer.Exit(code=handler(args))


def _build_typer_checks_app(command_module: ModuleType) -> typer.Typer:
    """Build the Typer checks app with nested command routing."""
    check_groups_help = "|".join(checks_module.list_check_groups())
    checks_app = typer.Typer(
        help="run repo-owned checks from repository configuration",
        add_completion=False,
        no_args_is_help=False,
    )

    @checks_app.command("run", help="run checks declared in repository configuration")
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
        all_phases: bool = typer.Option(
            False,
            "--all-phases",
            help="run checks across iteration_end, feature_done, and manual phases",
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
            normalized_checks = command_module.normalize_cli_checks_groups(checks)
        except ValueError as exc:
            print(str(exc))
            raise typer.Exit(code=1) from exc

        resolved_feature_path: str | None
        if feature_path is None:
            resolved_feature_path = None
        else:
            resolved_feature_path = str(feature_path).strip() or None

        _exit_with_handler_code(
            command_module.cmd_checks_run,
            ctx=ctx,
            checks=normalized_checks,
            check_id=check_id,
            feature_path=resolved_feature_path,
            phase=phase,
            all_phases=all_phases,
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
            command_module.cmd_checks_catalog,
            ctx=ctx,
            manifest_path=manifest_path,
            output_format=output_format,
            output=output,
        )

    return checks_app


def _dispatch_approach_command(
    command_module: ModuleType,
    *,
    ctx: typer.Context,
    topic_id: str | None,
    output: str | None,
) -> None:
    """Route approach topic requests to the correct handler."""
    if topic_id == "list":
        _exit_with_handler_code(
            command_module.cmd_approach_list,
            ctx=ctx,
            output=output,
        )
        return
    if topic_id is None:
        _exit_with_handler_code(
            command_module.cmd_approach_overview,
            ctx=ctx,
            output=output,
        )
        return

    _exit_with_handler_code(
        command_module.cmd_approach_show,
        ctx=ctx,
        topic_id=topic_id,
        output=output,
    )


def _dispatch_schema_command(
    command_module: ModuleType,
    *,
    ctx: typer.Context,
    schema_id: str | None,
    output_format: Literal["json", "yaml"],
    output: str | None,
) -> None:
    """Route schema commands to list or single-schema handler."""
    if schema_id == "list":
        _exit_with_handler_code(
            command_module.cmd_schema_list,
            ctx=ctx,
            output_format=output_format,
            output=output,
        )
        return

    kwargs = {"output_format": output_format, "output": output}
    if schema_id is not None:
        kwargs["schema_id"] = schema_id

    _exit_with_handler_code(
        command_module.cmd_schema,
        ctx=ctx,
        **kwargs,
    )


def build_typer_app(command_module: ModuleType) -> typer.Typer:
    """Build the Typer root app with top-level command wiring."""
    app = typer.Typer(
        name="engineeringagent",
        help="A framework for running coding agents as long-running tasks with deterministic feedback loops and agent reviewers",
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
            callback=command_module.version_callback,
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
            command_module.cmd_validate,
            ctx=ctx,
            schema_only=schema_only,
        )

    @app.command(
        "run",
        help="run feature loops from bundled spec.yaml entrypoint paths",
    )
    def _run_command(
        ctx: typer.Context,
        feature_paths: list[str] = typer.Argument(
            None,
            help="feature spec.yaml entrypoint paths",
        ),
        run_all: bool = typer.Option(
            False,
            "--all",
            help=(
                "auto-discover active feature entrypoints under "
                "docs/specifications/features"
            ),
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
            command_module.cmd_run,
            ctx=ctx,
            feature_paths=list(feature_paths or []),
            run_all=run_all,
            dry_run=dry_run,
            max_iterations=max_iterations,
            allow_dirty=allow_dirty,
            verbose_output=verbose_output,
        )

    app.add_typer(
        _build_typer_checks_app(command_module),
        name="checks",
        help="run repo-owned checks from repository configuration",
    )
    @app.command(
        "approach",
        help="open packaged approach guidance",
    )
    def _approach_command(
        ctx: typer.Context,
        topic_id: str | None = typer.Argument(
            None,
            help=(
                "optional approach topic id; use `list` to list available topics or "
                "omit for overview"
            ),
        ),
        output: str | None = typer.Option(
            None,
            "--output",
            help="optional path to write rendered output",
        ),
    ) -> None:
        _dispatch_approach_command(
            command_module,
            ctx=ctx,
            topic_id=topic_id,
            output=output,
        )

    @app.command(
        "schema",
        help="emit model-owned contract schemas (`schema list` or `schema <schema_id>`)",
    )
    def _schema_command(
        ctx: typer.Context,
        schema_id: str | None = typer.Argument(
            None,
            help="schema id to emit; use `list` to show available ids",
        ),
        output_format: Literal["json", "yaml"] = typer.Option(
            "json",
            "--format",
            help="schema output format",
        ),
        output: str | None = typer.Option(
            None,
            "--output",
            help="optional path to write schema output",
        ),
    ) -> None:
        _dispatch_schema_command(
            command_module,
            ctx=ctx,
            schema_id=schema_id,
            output_format=output_format,
            output=output,
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
        agents_launcher: str | None = typer.Option(
            None,
            "--agents-launcher",
            help="launcher wording for scaffolded AGENTS examples",
            click_type=click.Choice(list(AGENTS_LAUNCHER_CHOICES)),
        ),
        no_precommit_install: bool = typer.Option(
            False,
            "--no-precommit-install",
            help="skip best-effort pre-commit hook installation",
        ),
    ) -> None:
        _exit_with_handler_code(
            command_module.cmd_init,
            ctx=ctx,
            pack=pack,
            backend=backend,
            model=model,
            force=force,
            scaffold_profile=scaffold_profile,
            docs_mode=docs_mode,
            scaffold_docs_dir=scaffold_docs_dir,
            agents_mode=None,
            agents_launcher=agents_launcher,
            no_precommit_install=no_precommit_install,
        )

    workspace_app = typer.Typer(
        help="operate on isolated feature workspaces",
        add_completion=False,
        no_args_is_help=False,
    )

    @workspace_app.command(
        "reset",
        help="reset one feature workspace to the last accepted commit",
    )
    def _workspace_reset_command(
        ctx: typer.Context,
        feature_id: str = typer.Argument(
            ...,
            help="feature id whose workspace should be reset",
        ),
        last_accepted_commit: str = typer.Option(
            ...,
            "--last-accepted-commit",
            help="accepted commit to reset the workspace back to",
        ),
    ) -> None:
        _exit_with_handler_code(
            command_module.cmd_workspace_reset,
            ctx=ctx,
            feature_id=feature_id,
            last_accepted_commit=last_accepted_commit,
        )

    app.add_typer(
        workspace_app,
        name="workspace",
        help="operate on isolated feature workspaces",
    )

    return app
