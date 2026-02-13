from __future__ import annotations

import json
from pathlib import Path

import yaml

from .fitness import (
    DEPENDENCY_DIRECTIONALITY_RULE_ID,
    LOOP_SUBPROCESS_BOUNDARY_RULE_ID,
)
from .specs import feature_schema_from_model


def build_scaffold_agents_markdown() -> str:
    """Build baseline AGENTS.md guidance for scaffolded repositories."""
    return "\n".join(
        [
            "# AGENTS.md",
            "",
            "Agent operating guide for this repository.",
            "",
            "## Mission",
            "",
            "- Keep harness assets healthy and easy to validate.",
            "- Prefer safe, incremental updates over broad refactors.",
            "",
            "## Bootstrap",
            "",
            "- Ensure `harness/gates.yaml` exists and profiles reference valid gates.",
            "- Keep `docs/spec/` directories present for active, done, and backlog specs.",
            "- Keep pre-commit wired to the stable gate entrypoint.",
            "- Repair scaffold-managed assets with `engineeringagent init --force` when needed.",
            "",
            "## Validation",
            "",
            "- Validate feature schema and file structure: `engineeringagent validate`.",
            "- List configured gate profiles: `engineeringagent gates list`.",
            "- Execute a gate profile: `engineeringagent gates run --profile precommit`.",
            "",
        ]
    )


def build_agents_merge_followup_spec(backup_agents_name: str) -> str:
    """Build follow-up feature spec content for AGENTS merge work.

    Args:
        backup_agents_name: Backup AGENTS filename that should be merged.

    Returns:
        YAML text for a follow-up feature spec.
    """
    return yaml.safe_dump(
        {
            "id": "FEAT-900",
            "title": "Merge preserved AGENTS guidance into scaffold baseline",
            "status": "backlog",
            "priority": "medium",
            "objective": (
                "Compare preserved AGENTS guidance with scaffold AGENTS.md and "
                "reconcile repository-specific instructions."
            ),
            "acceptance": [
                f"Review `{backup_agents_name}` and `AGENTS.md` side by side.",
                "Capture durable merged guidance in `AGENTS.md`.",
                "Remove temporary notes once merge decisions are complete.",
            ],
        },
        sort_keys=False,
        allow_unicode=False,
    )


def build_baseline_scaffold_manifest(docs_dir: str = "docs") -> dict[str, str]:
    """Build the baseline scaffold manifest for a docs root.

    Args:
        docs_dir: Docs root directory where spec files should be scaffolded.

    Returns:
        Mapping of relative file paths to scaffolded file contents.
    """
    normalized_docs_dir = docs_dir.strip("/")

    return {
        ".pre-commit-config.yaml": "\n".join(
            [
                "repos:",
                "  - repo: local",
                "    hooks:",
                "      - id: engineeringagent-precommit",
                "        name: engineeringagent-precommit",
                "        entry: uvx --from . engineeringagent gates run --profile precommit",
                "        language: system",
                "        pass_filenames: false",
                "      - id: engineeringagent-commit-msg",
                "        name: engineeringagent-commit-msg",
                "        entry: uv run python harness/validate_commit_messages.py --commit-msg-file",
                "        language: system",
                "        stages: [commit-msg]",
                "",
            ]
        ),
        f"{normalized_docs_dir}/spec/features/.gitkeep": "",
        f"{normalized_docs_dir}/spec/features_done/.gitkeep": "",
        f"{normalized_docs_dir}/spec/potential_features.yaml": yaml.safe_dump(
            {
                "version": 1,
                "description": (
                    "Parking lot for future ideas that are intentionally not part of "
                    "active loop specs."
                ),
                "potential_features": [],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        f"{normalized_docs_dir}/spec/schemas/feature.schema.json": json.dumps(
            feature_schema_from_model(),
            indent=2,
        )
        + "\n",
        "harness/gates.yaml": yaml.safe_dump(
            {
                "profiles": {
                    "precommit": [],
                    "loop_fast": [],
                },
                "gates": {},
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        "harness/fitness-functions/rules.yaml": yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [
                    {"builtin": DEPENDENCY_DIRECTIONALITY_RULE_ID},
                    {"builtin": LOOP_SUBPROCESS_BOUNDARY_RULE_ID},
                ],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        "AGENTS.md": build_scaffold_agents_markdown(),
    }


def apply_baseline_scaffold(
    project_root: Path,
    force: bool = False,
    docs_dir: str = "docs",
) -> tuple[int, int]:
    """Write the baseline scaffold manifest to disk.

    Args:
        project_root: Repository root where scaffold files should be created.
        force: Whether to overwrite files that already exist.
        docs_dir: Docs root directory where spec files should be scaffolded.

    Returns:
        Tuple of (created_count, skipped_count).
    """
    created = 0
    skipped = 0

    manifest = build_baseline_scaffold_manifest(docs_dir=docs_dir)

    for relative_path, content in manifest.items():
        target_path = project_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if target_path.exists() and not force:
            skipped += 1
            continue

        target_path.write_text(content, encoding="utf-8")
        created += 1

    return created, skipped
