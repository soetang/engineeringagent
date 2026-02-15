from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from string import Template

import yaml

from .fitness import (
    DEPENDENCY_DIRECTIONALITY_RULE_ID,
    LOOP_SUBPROCESS_BOUNDARY_RULE_ID,
    SCAFFOLD_TEMPLATE_LOCALITY_RULE_ID,
)
from .specs import feature_schema_from_model


_SUPPORTED_SCAFFOLD_PROFILES = {"core", "python_uv"}
_SCAFFOLD_TEMPLATE_PACKAGE = "engineeringagent.scaffold_templates"


def _render_scaffold_template(
    name: str, substitutions: dict[str, str] | None = None
) -> str:
    """Render a scaffold template file with deterministic substitutions."""
    template_text = (
        files(_SCAFFOLD_TEMPLATE_PACKAGE).joinpath(name).read_text(encoding="utf-8")
    )
    if substitutions is None:
        return template_text
    return Template(template_text).substitute(substitutions)


def _build_precommit_config(profile: str) -> str:
    """Build pre-commit hook wiring for a scaffold profile."""
    if profile == "core":
        return _render_scaffold_template("precommit.core.yaml")

    if profile == "python_uv":
        return _render_scaffold_template("precommit.python_uv.yaml")

    raise ValueError(f"unsupported scaffold profile: {profile}")


def build_scaffold_agents_markdown() -> str:
    """Build baseline AGENTS.md guidance for scaffolded repositories."""
    return _render_scaffold_template("AGENTS.md")


def _build_reference_docs_manifest(docs_dir: str) -> dict[str, str]:
    """Build tool-generic agent docs references for the scaffold docs root."""
    return {
        f"{docs_dir}/references/docs-architecture-llms.md": _render_scaffold_template(
            "reference.docs-architecture-llms.md"
        ),
        f"{docs_dir}/references/workflow-llms.md": _render_scaffold_template(
            "reference.workflow-llms.md"
        ),
    }


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


def build_baseline_scaffold_manifest(
    docs_dir: str = "docs",
    profile: str = "core",
    include_reviewers: bool = False,
) -> dict[str, str]:
    """Build the baseline scaffold manifest for a docs root.

    Args:
        docs_dir: Docs root directory where spec files should be scaffolded.
        profile: Scaffold profile that determines language/tool defaults.
        include_reviewers: Backward-compatible no-op; init does not seed reviewers.

    Returns:
        Mapping of relative file paths to scaffolded file contents.
    """
    if profile not in _SUPPORTED_SCAFFOLD_PROFILES:
        raise ValueError(f"unsupported scaffold profile: {profile}")

    normalized_docs_dir = docs_dir.strip("/")

    manifest = {
        ".pre-commit-config.yaml": _build_precommit_config(profile=profile),
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
                    {"builtin": SCAFFOLD_TEMPLATE_LOCALITY_RULE_ID},
                ],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        "AGENTS.md": build_scaffold_agents_markdown(),
        **_build_reference_docs_manifest(normalized_docs_dir),
    }

    return manifest


def apply_baseline_scaffold(
    project_root: Path,
    force: bool = False,
    docs_dir: str = "docs",
    profile: str = "core",
    include_reviewers: bool = False,
) -> tuple[int, int]:
    """Write the baseline scaffold manifest to disk.

    Args:
        project_root: Repository root where scaffold files should be created.
        force: Whether to overwrite files that already exist.
        docs_dir: Docs root directory where spec files should be scaffolded.
        profile: Scaffold profile that determines language/tool defaults.
        include_reviewers: Backward-compatible no-op; init does not seed reviewers.

    Returns:
        Tuple of (created_count, skipped_count).
    """
    created = 0
    skipped = 0

    manifest = build_baseline_scaffold_manifest(
        docs_dir=docs_dir,
        profile=profile,
        include_reviewers=include_reviewers,
    )

    for relative_path, content in manifest.items():
        target_path = project_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if target_path.exists() and not force:
            skipped += 1
            continue

        target_path.write_text(content, encoding="utf-8")
        created += 1

    return created, skipped
