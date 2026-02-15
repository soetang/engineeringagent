from __future__ import annotations

import importlib.metadata
import json
import sys
from collections.abc import Callable
from pathlib import Path
from types import SimpleNamespace
from typing import Literal

import typer

from .fitness import (
    FitnessRuleDefinition,
    RuleStatus,
    build_rule_catalog,
    render_rule_catalog_markdown,
    run_rule_catalog,
    write_rule_catalog_markdown,
)
from .gates import (
    collect_changed_paths,
    list_profiles,
    load_gate_config,
    plan_profile,
    run_profile,
)
from .init_scaffold import (
    apply_baseline_scaffold,
    build_agents_merge_followup_spec,
    build_scaffold_agents_markdown,
)
from .loop import run_loop
from .opencode.client import start_agent
from .reviewers import (
    REVIEWER_RESPONSEFORMAT_PLACEHOLDER,
    load_reviewer_config,
    plan_reviewers,
    run_reviewer,
)
from .validator import validate

_MISSING_REMEDIATION_TEMPLATE = (
    "No remediation available: rule metadata missing from active catalog for {rule_id}."
)

_HandlerArgs = SimpleNamespace


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


def _fitness_metadata_payload(
    definition: FitnessRuleDefinition,
    *,
    include_details: bool,
) -> dict[str, object]:
    """Serialize rule metadata into deterministic JSON payload fields."""
    metadata = definition.metadata
    payload: dict[str, object] = {
        "rule_id": metadata.rule_id,
        "name": metadata.name,
        "summary": metadata.summary,
        "scope": metadata.scope,
        "severity": metadata.severity.value,
        "adapter": metadata.adapter.value,
        "source": metadata.source.value,
        "side_effect_free": metadata.side_effect_free,
    }
    if include_details:
        payload["rationale"] = metadata.rationale
        payload["remediation"] = metadata.remediation
    return payload


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


def cmd_validate(args: _HandlerArgs) -> int:
    """Run feature spec validation and print failures.

    Args:
        args: Parsed CLI arguments for the validate subcommand.

    Returns:
        Process exit code where 0 means validation passed.
    """
    project_root = Path(args.project_root).resolve()
    messages = validate(project_root=project_root, schema_only=args.schema_only)
    if messages:
        for msg in messages:
            print(msg)
        return 1
    print("spec validation: ok")
    return 0


def cmd_gates_list(args: _HandlerArgs) -> int:
    """List configured gate profiles.

    Args:
        args: Parsed CLI arguments for the gates list subcommand.

    Returns:
        Process exit code where 0 means success.
    """
    project_root = Path(args.project_root).resolve()
    config = load_gate_config(project_root / "harness" / "gates.yaml")
    for name in list_profiles(config):
        print(name)
    return 0


def cmd_gates_run(args: _HandlerArgs) -> int:
    """Run a configured gate profile.

    Args:
        args: Parsed CLI arguments for the gates run subcommand.

    Returns:
        Process exit code where 0 means all gates passed.
    """
    project_root = Path(args.project_root).resolve()
    config = load_gate_config(project_root / "harness" / "gates.yaml")
    profiles = config.get("profiles", {})
    profile_gates = profiles.get(args.profile, []) if isinstance(profiles, dict) else []
    if isinstance(profile_gates, list) and len(profile_gates) == 0:
        print(f"gates profile has no configured gates: {args.profile}")
        return 0

    changed_paths = collect_changed_paths(
        project_root,
        base=getattr(args, "base", None),
        head=getattr(args, "head", None),
    )
    if getattr(args, "explain", False):
        decisions = plan_profile(
            config,
            args.profile,
            changed_paths=changed_paths,
        )
        print(json.dumps(decisions, sort_keys=True))

    ok, failed, _ = run_profile(
        config=config,
        profile=args.profile,
        cwd=project_root,
        changed_paths=changed_paths,
    )
    if not ok:
        print(f"gates profile failed: {failed}")
        return 1
    print(f"gates profile passed: {args.profile}")
    return 0


def cmd_gates_plan(args: _HandlerArgs) -> int:
    """Print deterministic run/skip gate decisions for one profile."""
    project_root = Path(args.project_root).resolve()
    config = load_gate_config(project_root / "harness" / "gates.yaml")
    changed_paths = collect_changed_paths(
        project_root,
        base=args.base,
        head=args.head,
    )
    decisions = plan_profile(config, args.profile, changed_paths=changed_paths)
    print(json.dumps(decisions, sort_keys=True))
    return 0


def cmd_run(args: _HandlerArgs) -> int:
    """Execute the loop runner for one or more feature files.

    Args:
        args: Parsed CLI arguments for the run subcommand.

    Returns:
        Process exit code from the loop runner.
    """
    if args.all and args.feature_paths:
        print("run input error: positional feature paths cannot be used with --all")
        return 1
    if not args.all and not args.feature_paths:
        print("run input error: provide one or more feature paths, or use --all")
        return 1

    project_root = Path(args.project_root).resolve()
    return run_loop(
        project_root=project_root,
        feature_paths=args.feature_paths,
        run_all=args.all,
        gate_profile=getattr(args, "gate_profile", "loop_fast"),
        implement_command=args.implement_command,
        skip_implement=args.skip_implement,
        dry_run=args.dry_run,
        max_iterations=args.max_iterations,
        allow_dirty=args.allow_dirty,
        verbose_output=args.verbose_output,
    )


def cmd_reviewers_list(args: _HandlerArgs) -> int:
    """List configured reviewer profiles."""
    project_root = Path(args.project_root).resolve()
    config = load_reviewer_config(project_root / "harness" / "reviewers.yaml")
    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict):
        return 0
    for profile in sorted(profiles):
        print(profile)
    return 0


def cmd_reviewers_plan(args: _HandlerArgs) -> int:
    """Print deterministic run/skip reviewer decisions for one profile/phase."""
    project_root = Path(args.project_root).resolve()
    config = load_reviewer_config(project_root / "harness" / "reviewers.yaml")
    changed_paths = collect_changed_paths(
        project_root,
        base=args.base,
        head=args.head,
    )
    try:
        decisions = plan_reviewers(
            config,
            args.profile,
            phase=args.phase,
            changed_paths=changed_paths,
        )
    except ValueError as exc:
        print(str(exc))
        return 1
    print(json.dumps(decisions, sort_keys=True))
    return 0


def cmd_reviewers_run(args: _HandlerArgs) -> int:
    """Run one configured reviewer and print JSON decision envelope."""
    project_root = Path(args.project_root).resolve()
    config = load_reviewer_config(project_root / "harness" / "reviewers.yaml")
    reviewers = config.get("reviewers", {})
    reviewer = reviewers.get(args.reviewer) if isinstance(reviewers, dict) else None
    if not isinstance(reviewer, dict):
        print(f"unknown reviewer: {args.reviewer}")
        return 1

    changed_paths = collect_changed_paths(
        project_root,
        base=args.base,
        head=args.head,
    )
    feature_path = Path(args.feature_path)
    if not feature_path.is_absolute():
        feature_path = project_root / feature_path

    decision = run_reviewer(
        project_root,
        args.reviewer,
        reviewer,
        feature_id=args.feature_id,
        feature_path=feature_path,
        changed_paths=changed_paths,
        prior_feedback=args.prior_feedback,
        start_agent_fn=start_agent,
    )
    print(json.dumps(decision, sort_keys=True))
    return 0 if decision.get("decision") != "request_changes" else 1


def cmd_reviewers_init(args: _HandlerArgs) -> int:
    """Write a baseline reviewers config and prompt files."""
    project_root = Path(args.project_root).resolve()
    created = 0
    skipped = 0

    manifest = {
        "harness/reviewers.yaml": "\n".join(
            [
                'contract_version: "1.0"',
                "profiles:",
                "  loop_fast:",
                "    - code_simplifier",
                "    - readme_process",
                "reviewers:",
                "  code_simplifier:",
                '    prompt_file: "harness/reviewers/prompts/code_simplifier.md"',
                "    trigger:",
                '      phase: "iteration_end"',
                "      on_change:",
                '        - "src/**/*.py"',
                '        - "tests/**/*.py"',
                "    approval:",
                '      mode: "advisory"',
                "  readme_process:",
                '    prompt_file: "harness/reviewers/prompts/readme_process.md"',
                "    trigger:",
                '      phase: "feature_done"',
                '      on_change: ["README.md"]',
                "    sandbox:",
                '      mode: "temp_worktree_snapshot"',
                "    approval:",
                '      mode: "blocking"',
                "",
            ]
        ),
        "harness/reviewers/prompts/code_simplifier.md": "\n".join(
            [
                "Review only the scoped changed files for readability and maintainability.",
                REVIEWER_RESPONSEFORMAT_PLACEHOLDER,
                "",
            ]
        ),
        "harness/reviewers/prompts/readme_process.md": "\n".join(
            [
                "Review README workflow/process guidance for correctness and clarity.",
                REVIEWER_RESPONSEFORMAT_PLACEHOLDER,
                "",
            ]
        ),
    }

    for relative_path, content in manifest.items():
        target = project_root / relative_path
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists() and not args.force:
            skipped += 1
            continue
        target.write_text(content, encoding="utf-8")
        created += 1

    print(f"reviewers init complete: created={created} skipped={skipped}")
    return 0


def cmd_fitness_list(args: _HandlerArgs) -> int:
    """List active fitness rules from the merged registry."""
    project_root = Path(args.project_root).resolve()
    manifest_path = _resolve_manifest_path(args.manifest_path)
    catalog = build_rule_catalog(project_root, manifest_path=manifest_path)

    if args.format == "json":
        payload = [
            _fitness_metadata_payload(definition, include_details=False)
            for definition in catalog
        ]
        print(json.dumps(payload, indent=2, sort_keys=True))
        return 0

    if not catalog:
        print("No active fitness rules found.")
        return 0

    for definition in catalog:
        metadata = definition.metadata
        print(
            f"{metadata.rule_id} [{metadata.severity.value}] "
            f"({metadata.adapter.value}/{metadata.source.value}) - {metadata.summary}"
        )
    return 0


def cmd_fitness_run(args: _HandlerArgs) -> int:
    """Execute active fitness rules and return deterministic status."""
    project_root = Path(args.project_root).resolve()
    manifest_path = _resolve_manifest_path(args.manifest_path)
    catalog = build_rule_catalog(project_root, manifest_path=manifest_path)
    remediation_by_rule_id = {
        definition.metadata.rule_id: definition.metadata.remediation
        for definition in catalog
    }
    summary = run_rule_catalog(
        project_root,
        jobs=args.jobs,
        manifest_path=manifest_path,
    )

    failed_rules = [
        {
            "rule_id": result.rule_id,
            "status": result.status.value,
            "remediation": _resolve_failed_rule_remediation(
                rule_id=result.rule_id,
                remediation_by_rule_id=remediation_by_rule_id,
            ),
        }
        for result in summary.results
        if result.status in {RuleStatus.FAIL, RuleStatus.ERROR}
    ]

    if args.format == "json":
        payload = {
            "results": [result.model_dump(mode="json") for result in summary.results],
            "failed_rules": failed_rules,
            "failed": summary.has_failures,
        }
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        if not summary.results:
            print("No active fitness rules found.")
        for result in summary.results:
            print(f"{result.rule_id}: {result.status.value} - {result.summary}")

    if summary.has_failures:
        return 1
    return 0


def _resolve_failed_rule_remediation(
    *,
    rule_id: str,
    remediation_by_rule_id: dict[str, str],
) -> str:
    """Return deterministic remediation text for failed-rule JSON output."""
    return remediation_by_rule_id.get(
        rule_id,
        _MISSING_REMEDIATION_TEMPLATE.format(rule_id=rule_id),
    )


def cmd_fitness_catalog(args: _HandlerArgs) -> int:
    """Generate the fitness-rule catalog from active registry metadata."""
    project_root = Path(args.project_root).resolve()
    manifest_path = _resolve_manifest_path(args.manifest_path)
    output_path = _resolve_optional_path(path=args.output, project_root=project_root)

    catalog = build_rule_catalog(project_root, manifest_path=manifest_path)

    if args.format == "json":
        payload = [
            _fitness_metadata_payload(definition, include_details=True)
            for definition in catalog
        ]
        rendered = json.dumps(payload, indent=2, sort_keys=True)
    else:
        rendered = render_rule_catalog_markdown(catalog)

    if output_path is not None:
        write_rule_catalog_markdown(output_path, rendered + "\n")
        try:
            shown_path = output_path.relative_to(project_root)
        except ValueError:
            shown_path = output_path
        print(f"fitness catalog written: {shown_path}")
        return 0

    print(rendered)
    return 0


def cmd_init(args: _HandlerArgs) -> int:
    """Scaffold baseline harness files for a repository.

    Args:
        args: Parsed CLI arguments for the init subcommand.

    Returns:
        Process exit code where 0 means success.
    """
    project_root = Path(args.project_root).resolve()
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
        force=args.force,
        docs_dir=docs_dir,
        profile=args.scaffold_profile,
    )
    config_created, config_skipped = _write_init_docs_root_config(
        project_root,
        docs_dir,
        force=args.force,
    )
    created += config_created
    skipped += config_skipped

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

    agents_mode_output = f" agents_mode={resolved_agents_mode}"
    if agents_backup_name is not None:
        agents_mode_output += f" agents_backup={agents_backup_name}"

    print(
        f"init scaffold complete: docs_dir={docs_dir} "
        f"created={created} skipped={skipped}"
        f" profile={args.scaffold_profile}"
        f"{agents_mode_output}{merge_spec_output}"
    )
    return 0


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


def _build_typer_gates_app() -> typer.Typer:
    """Build the Typer gates app with nested command routing."""
    gates_app = typer.Typer(
        help="run configured gate profiles",
        add_completion=False,
        no_args_is_help=False,
    )

    @gates_app.command("list", help="list gate profiles")
    def _gates_list(ctx: typer.Context) -> None:
        _exit_with_handler_code(cmd_gates_list, ctx=ctx)

    @gates_app.command("plan", help="show deterministic gate run/skip plan")
    def _gates_plan(
        ctx: typer.Context,
        profile: str = typer.Option(..., "--profile"),
        base: str | None = typer.Option(None, "--base"),
        head: str | None = typer.Option(None, "--head"),
    ) -> None:
        _exit_with_handler_code(
            cmd_gates_plan,
            ctx=ctx,
            profile=profile,
            base=base,
            head=head,
        )

    @gates_app.command("run", help="run a gate profile")
    def _gates_run(
        ctx: typer.Context,
        profile: str = typer.Option(..., "--profile"),
        base: str | None = typer.Option(None, "--base"),
        head: str | None = typer.Option(None, "--head"),
        explain: bool = typer.Option(False, "--explain"),
    ) -> None:
        _exit_with_handler_code(
            cmd_gates_run,
            ctx=ctx,
            profile=profile,
            base=base,
            head=head,
            explain=explain,
        )

    return gates_app


def _build_typer_reviewers_app() -> typer.Typer:
    """Build the Typer reviewers app with nested command routing."""
    reviewers_app = typer.Typer(
        help="initialize, inspect, and run harness reviewers",
        add_completion=False,
        no_args_is_help=False,
    )

    @reviewers_app.command(
        "init",
        help="write baseline reviewers.yaml and prompt files",
    )
    def _reviewers_init(
        ctx: typer.Context,
        force: bool = typer.Option(
            False,
            "--force",
            help="overwrite existing reviewer scaffold files",
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_reviewers_init,
            ctx=ctx,
            force=force,
        )

    @reviewers_app.command("list", help="list reviewer profiles")
    def _reviewers_list(ctx: typer.Context) -> None:
        _exit_with_handler_code(cmd_reviewers_list, ctx=ctx)

    @reviewers_app.command("plan", help="show deterministic reviewer run/skip plan")
    def _reviewers_plan(
        ctx: typer.Context,
        profile: str = typer.Option(..., "--profile"),
        phase: Literal["iteration_end", "feature_done"] = typer.Option(
            ...,
            "--phase",
        ),
        base: str | None = typer.Option(None, "--base"),
        head: str | None = typer.Option(None, "--head"),
    ) -> None:
        _exit_with_handler_code(
            cmd_reviewers_plan,
            ctx=ctx,
            profile=profile,
            phase=phase,
            base=base,
            head=head,
        )

    @reviewers_app.command("run", help="run one reviewer and print decision JSON")
    def _reviewers_run(
        ctx: typer.Context,
        reviewer: str = typer.Option(..., "--reviewer"),
        feature_id: str = typer.Option(..., "--feature-id"),
        feature_path: str = typer.Option(
            ...,
            "--feature-path",
            help="feature spec path used in reviewer context",
        ),
        prior_feedback: str | None = typer.Option(None, "--prior-feedback"),
        base: str | None = typer.Option(None, "--base"),
        head: str | None = typer.Option(None, "--head"),
    ) -> None:
        _exit_with_handler_code(
            cmd_reviewers_run,
            ctx=ctx,
            reviewer=reviewer,
            feature_id=feature_id,
            feature_path=feature_path,
            prior_feedback=prior_feedback,
            base=base,
            head=head,
        )

    return reviewers_app


def _build_typer_fitness_app() -> typer.Typer:
    """Build the Typer fitness app with nested command routing."""
    fitness_app = typer.Typer(
        help="list and run fitness-function rules",
        add_completion=False,
        no_args_is_help=False,
    )

    @fitness_app.command("list", help="list active fitness rules")
    def _fitness_list(
        ctx: typer.Context,
        manifest_path: str | None = typer.Option(
            None,
            "--manifest-path",
            help="optional path to custom fitness rules manifest",
        ),
        output_format: Literal["text", "json"] = typer.Option(
            "text",
            "--format",
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_fitness_list,
            ctx=ctx,
            manifest_path=manifest_path,
            format=output_format,
        )

    @fitness_app.command("run", help="run active fitness rules")
    def _fitness_run(
        ctx: typer.Context,
        manifest_path: str | None = typer.Option(
            None,
            "--manifest-path",
            help="optional path to custom fitness rules manifest",
        ),
        jobs: int = typer.Option(
            1,
            "--jobs",
            help="number of parallel fitness-rule workers",
        ),
        output_format: Literal["text", "json"] = typer.Option(
            "text",
            "--format",
        ),
    ) -> None:
        _exit_with_handler_code(
            cmd_fitness_run,
            ctx=ctx,
            manifest_path=manifest_path,
            jobs=jobs,
            format=output_format,
        )

    @fitness_app.command("catalog", help="generate fitness rule catalog")
    def _fitness_catalog(
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
            cmd_fitness_catalog,
            ctx=ctx,
            manifest_path=manifest_path,
            format=output_format,
            output=output,
        )

    return fitness_app


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

    app.add_typer(
        _build_typer_gates_app(),
        name="gates",
        help="run configured gate profiles",
    )
    app.add_typer(
        _build_typer_reviewers_app(),
        name="reviewers",
        help="initialize, inspect, and run harness reviewers",
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
        implement_command: str | None = typer.Option(
            None,
            "--implement-command",
            help="custom implementation command; defaults to opencode build-agent run",
        ),
        skip_implement: bool = typer.Option(
            False,
            "--skip-implement",
            help="skip the implementation command and run gates only",
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
            all=run_all,
            implement_command=implement_command,
            skip_implement=skip_implement,
            dry_run=dry_run,
            max_iterations=max_iterations,
            allow_dirty=allow_dirty,
            verbose_output=verbose_output,
            gate_profile="loop_fast",
        )

    app.add_typer(
        _build_typer_fitness_app(),
        name="fitness",
        help="list and run fitness-function rules",
    )

    @app.command(
        "init",
        help="scaffold baseline harness files (default core profile)",
    )
    def _init_command(
        ctx: typer.Context,
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
    ) -> None:
        _exit_with_handler_code(
            cmd_init,
            ctx=ctx,
            force=force,
            scaffold_profile=scaffold_profile,
            docs_mode=docs_mode,
            scaffold_docs_dir=scaffold_docs_dir,
            agents_mode=None,
        )

    return app


def main(argv: list[str] | None = None) -> None:
    """Parse CLI arguments with Typer and exit with command status."""
    app = build_typer_app()
    app(args=argv, prog_name="engineeringagent")


if __name__ == "__main__":
    sys.exit(main())
