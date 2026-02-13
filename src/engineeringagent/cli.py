from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .fitness import (
    build_rule_catalog,
    render_rule_catalog_markdown,
    run_rule_catalog,
    write_rule_catalog_markdown,
)
from .gates import list_profiles, load_gate_config, run_profile
from .init_scaffold import (
    apply_baseline_scaffold,
    build_agents_merge_followup_spec,
    build_scaffold_agents_markdown,
)
from .loop import run_loop
from .validator import validate


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


def cmd_validate(args: argparse.Namespace) -> int:
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


def cmd_gates_list(args: argparse.Namespace) -> int:
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


def cmd_gates_run(args: argparse.Namespace) -> int:
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

    ok, failed, _ = run_profile(config=config, profile=args.profile, cwd=project_root)
    if not ok:
        print(f"gates profile failed: {failed}")
        return 1
    print(f"gates profile passed: {args.profile}")
    return 0


def cmd_run(args: argparse.Namespace) -> int:
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
        gate_profile=args.gate_profile,
        implement_command=args.implement_command,
        opencode_prompt=args.opencode_prompt,
        skip_implement=args.skip_implement,
        dry_run=args.dry_run,
        max_iterations=args.max_iterations,
        allow_dirty=args.allow_dirty,
        verbose_output=args.verbose_output,
    )


def cmd_fitness_list(args: argparse.Namespace) -> int:
    """List active fitness rules from the merged registry."""
    project_root = Path(args.project_root).resolve()
    manifest_path = Path(args.manifest_path) if args.manifest_path else None
    catalog = build_rule_catalog(project_root, manifest_path=manifest_path)

    if args.format == "json":
        payload = [
            {
                "rule_id": definition.metadata.rule_id,
                "name": definition.metadata.name,
                "summary": definition.metadata.summary,
                "severity": definition.metadata.severity.value,
                "adapter": definition.metadata.adapter.value,
                "source": definition.metadata.source.value,
                "scope": definition.metadata.scope,
                "side_effect_free": definition.metadata.side_effect_free,
            }
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


def cmd_fitness_run(args: argparse.Namespace) -> int:
    """Execute active fitness rules and return deterministic status."""
    project_root = Path(args.project_root).resolve()
    manifest_path = Path(args.manifest_path) if args.manifest_path else None
    summary = run_rule_catalog(
        project_root,
        jobs=args.jobs,
        manifest_path=manifest_path,
    )

    if args.format == "json":
        payload = {
            "results": [result.model_dump(mode="json") for result in summary.results],
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


def cmd_fitness_catalog(args: argparse.Namespace) -> int:
    """Generate the fitness-rule catalog from active registry metadata."""
    project_root = Path(args.project_root).resolve()
    manifest_path = Path(args.manifest_path) if args.manifest_path else None
    output_path = Path(args.output) if args.output else None
    if output_path is not None and not output_path.is_absolute():
        output_path = project_root / output_path

    catalog = build_rule_catalog(project_root, manifest_path=manifest_path)

    if args.format == "json":
        payload = [
            {
                "rule_id": definition.metadata.rule_id,
                "name": definition.metadata.name,
                "summary": definition.metadata.summary,
                "rationale": definition.metadata.rationale,
                "remediation": definition.metadata.remediation,
                "scope": definition.metadata.scope,
                "severity": definition.metadata.severity.value,
                "adapter": definition.metadata.adapter.value,
                "source": definition.metadata.source.value,
                "side_effect_free": definition.metadata.side_effect_free,
            }
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


def cmd_init(args: argparse.Namespace) -> int:
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
        agents_mode=args.agents_mode,
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
    )

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
        f"{agents_mode_output}{merge_spec_output}"
    )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Build the root CLI parser with all subcommands.

    Returns:
        Configured argument parser for the engineeringagent CLI.
    """
    parser = argparse.ArgumentParser(
        prog="engineeringagent",
        description="Human-gated CLI harness for feature-driven coding loops.",
    )
    parser.add_argument("--project-root", default=".")
    sub = parser.add_subparsers(dest="command", required=True)

    validate_parser = sub.add_parser("validate", help="validate feature specs")
    validate_parser.add_argument("--schema-only", action="store_true")
    validate_parser.set_defaults(func=cmd_validate)

    gates_parser = sub.add_parser("gates", help="run configured gate profiles")
    gates_sub = gates_parser.add_subparsers(dest="gates_cmd", required=True)

    gates_list_parser = gates_sub.add_parser("list", help="list gate profiles")
    gates_list_parser.set_defaults(func=cmd_gates_list)

    gates_run_parser = gates_sub.add_parser("run", help="run a gate profile")
    gates_run_parser.add_argument("--profile", required=True)
    gates_run_parser.set_defaults(func=cmd_gates_run)

    run_parser = sub.add_parser("run", help="run feature loops from spec file paths")
    run_parser.add_argument("feature_paths", nargs="*", help="feature spec file paths")
    run_parser.add_argument(
        "--all",
        action="store_true",
        help="auto-discover active feature specs under docs/spec/features",
    )
    run_parser.add_argument(
        "--gate-profile", default="loop_fast", help="gate profile name"
    )
    run_parser.add_argument(
        "--implement-command",
        help="custom implementation command; defaults to opencode build-agent run",
    )
    run_parser.add_argument(
        "--opencode-prompt",
        help="override generated opencode prompt when using default implementer",
    )
    run_parser.add_argument(
        "--skip-implement",
        action="store_true",
        help="skip the implementation command and run gates only",
    )
    run_parser.add_argument("--dry-run", action="store_true")
    run_parser.add_argument(
        "--max-iterations",
        type=int,
        default=50,
        help="max non-dry iterations across all selected features",
    )
    run_parser.add_argument(
        "--allow-dirty",
        action="store_true",
        help="allow run execution with uncommitted code changes",
    )
    run_parser.add_argument(
        "--verbose-output",
        action="store_true",
        help="stream full implement and gate output in terminal",
    )
    run_parser.set_defaults(func=cmd_run)

    fitness_parser = sub.add_parser(
        "fitness", help="list and run fitness-function rules"
    )
    fitness_sub = fitness_parser.add_subparsers(dest="fitness_cmd", required=True)

    fitness_list_parser = fitness_sub.add_parser(
        "list", help="list active fitness rules"
    )
    fitness_list_parser.add_argument(
        "--manifest-path",
        help="optional path to custom fitness rules manifest",
    )
    fitness_list_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
    )
    fitness_list_parser.set_defaults(func=cmd_fitness_list)

    fitness_run_parser = fitness_sub.add_parser("run", help="run active fitness rules")
    fitness_run_parser.add_argument(
        "--manifest-path",
        help="optional path to custom fitness rules manifest",
    )
    fitness_run_parser.add_argument(
        "--jobs",
        type=int,
        default=1,
        help="number of parallel fitness-rule workers",
    )
    fitness_run_parser.add_argument(
        "--format",
        choices=["text", "json"],
        default="text",
    )
    fitness_run_parser.set_defaults(func=cmd_fitness_run)

    fitness_catalog_parser = fitness_sub.add_parser(
        "catalog", help="generate fitness rule catalog"
    )
    fitness_catalog_parser.add_argument(
        "--manifest-path",
        help="optional path to custom fitness rules manifest",
    )
    fitness_catalog_parser.add_argument(
        "--format",
        choices=["markdown", "json"],
        default="markdown",
    )
    fitness_catalog_parser.add_argument(
        "--output",
        help="write catalog output to a file",
    )
    fitness_catalog_parser.set_defaults(func=cmd_fitness_catalog)

    init_parser = sub.add_parser(
        "init", help="scaffold baseline harness files for this repository"
    )
    init_parser.add_argument(
        "--force",
        action="store_true",
        help="overwrite scaffold-managed files that already exist",
    )
    init_parser.add_argument(
        "--docs-mode",
        choices=["reuse", "separate"],
        help="docs conflict mode when docs/ already exists",
    )
    init_parser.add_argument(
        "--scaffold-docs-dir",
        default="docs.engineeringagent",
        help="docs directory to scaffold when using docs-mode=separate",
    )
    init_parser.add_argument(
        "--agents-mode",
        choices=["overwrite", "preserve", "abort"],
        help="AGENTS conflict mode when AGENTS.md already exists",
    )
    init_parser.set_defaults(func=cmd_init)

    return parser


def main() -> None:
    """Parse CLI arguments and exit with the command status."""
    parser = build_parser()
    args = parser.parse_args()
    code = args.func(args)
    raise SystemExit(code)


if __name__ == "__main__":
    sys.exit(main())
