from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from string import Template

import yaml

from .specs import feature_schema_from_model


_SUPPORTED_SCAFFOLD_PROFILES = {"core", "python_uv"}
_SCAFFOLD_TEMPLATE_PACKAGE = "engineeringagent.scaffold_templates"

_SUPPORTED_INIT_PACKS = {"slim", "standard"}


def _spec_validate_gate(docs_dir_normalized: str) -> dict[str, object]:
    """Return a stable spec validation gate config for harness profiles."""

    return {
        "run": "engineeringagent validate",
        "on_change": [
            f"{docs_dir_normalized}/spec/**/*.yaml",
            f"{docs_dir_normalized}/spec/**/*.yml",
            f"{docs_dir_normalized}/spec/**/*.json",
        ],
    }


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


def _build_reference_docs_manifest() -> dict[str, str]:
    """Build tool-generic agent docs references.

    Note: These are kept under the default `docs/` directory even when feature specs
    are configured to live under a separate docs root.
    """
    return {
        "docs/references/docs-architecture-llms.md": _render_scaffold_template(
            "reference.docs-architecture-llms.md"
        ),
        "docs/references/workflow-llms.md": _render_scaffold_template(
            "reference.workflow-llms.md"
        ),
        "docs/references/spec-writing-llms.md": _render_scaffold_template(
            "reference.spec-writing-llms.md"
        ),
    }


def _build_opencode_scaffold_manifest() -> dict[str, str]:
    """Build baseline `.opencode/` scaffold files.

    Template sources (for deterministic reference coverage):
    - src/engineeringagent/scaffold_templates/opencode.agent.engineeringagent.md
    - src/engineeringagent/scaffold_templates/opencode.gitignore
    """
    return {
        ".opencode/agents/engineeringagent.md": _render_scaffold_template(
            "opencode.agent.engineeringagent.md"
        ),
        ".opencode/.gitignore": _render_scaffold_template("opencode.gitignore"),
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

    docs_dir_normalized = docs_dir.strip("/")
    is_python_uv = profile == "python_uv"
    gate_config = {
        "contract_version": "1.0",
        "profiles": {
            "precommit": ["spec_validate"],
            "loop_fast": ["spec_validate"],
        },
        "gates": {
            "spec_validate": _spec_validate_gate(docs_dir_normalized),
        },
    }

    if is_python_uv:
        gate_config["profiles"]["precommit"] = ["spec_validate", "ruff_validate"]
        gate_config["gates"]["ruff_validate"] = {
            "run": "uvx ruff check --isolated .",
        }

    manifest = {
        ".pre-commit-config.yaml": _build_precommit_config(profile=profile),
        **_build_opencode_scaffold_manifest(),
        f"{docs_dir_normalized}/spec/features/.gitkeep": "",
        f"{docs_dir_normalized}/spec/features_done/.gitkeep": "",
        f"{docs_dir_normalized}/spec/potential_features.yaml": yaml.safe_dump(
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
        f"{docs_dir_normalized}/spec/schemas/feature.schema.json": json.dumps(
            feature_schema_from_model(),
            indent=2,
        )
        + "\n",
        "harness/gates.yaml": yaml.safe_dump(
            gate_config,
            sort_keys=False,
            allow_unicode=False,
        ),
        "harness/fitness-functions/rules.yaml": yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        "AGENTS.md": build_scaffold_agents_markdown(),
        **_build_reference_docs_manifest(),
    }

    if is_python_uv:
        manifest["harness/fitness-functions/validate_commit_messages.py"] = (
            _render_scaffold_template("fitness.validate_commit_messages.py")
        )

    return manifest


def _demo_fail_rule_script() -> str:
    """Return a deterministic script body that emits a failing rule envelope."""
    return (
        "from __future__ import annotations\n"
        "\n"
        "import json\n"
        "\n"
        "\n"
        "def main() -> None:\n"
        "    payload = {\n"
        '        "contract_version": "1.0",\n'
        '        "rule_id": "demo.always-fail",\n'
        '        "status": "fail",\n'
        '        "severity": "error",\n'
        '        "summary": "Demo failing rule (standard init pack).",\n'
        '        "violations": ["Demo rule triggered to show pre-commit failure output."],\n'
        "    }\n"
        "    print(json.dumps(payload, sort_keys=True))\n"
        "\n"
        "\n"
        'if __name__ == "__main__":\n'
        "    main()\n"
    )


def build_init_scaffold_manifest(
    *,
    docs_dir: str = "docs",
    profile: str = "core",
    pack: str = "slim",
    include_reviewers: bool = False,
) -> dict[str, str]:
    """Build init scaffold manifest for the selected pack.

    Packs:
    - slim: safe default that runs spec validation
    - standard: wires an always-failing demo fitness rule into pre-commit gates
    """
    if pack not in _SUPPORTED_INIT_PACKS:
        raise ValueError(f"unsupported init pack: {pack}")

    manifest = build_baseline_scaffold_manifest(
        docs_dir=docs_dir,
        profile=profile,
        include_reviewers=include_reviewers,
    )

    if pack != "standard":
        return manifest

    demo_manifest_path = "harness/fitness-functions/demo_rules.yaml"
    demo_script_path = "harness/fitness-functions/demo_always_fail.py"
    manifest[demo_manifest_path] = yaml.safe_dump(
        {
            "contract_version": "1.0",
            "rules": [
                {
                    "rule_id": "demo.always-fail",
                    "name": "Demo always failing rule",
                    "summary": "Demonstration rule that always fails.",
                    "rationale": (
                        "Provides an immediate example of a failing fitness rule in pre-commit."
                    ),
                    "remediation": (
                        "Disable the demo by removing gate 'demo_fail' from harness/gates.yaml and deleting "
                        "harness/fitness-functions/demo_rules.yaml (or re-run: engineeringagent init slim --force)."
                    ),
                    "scope": ".",
                    "severity": "error",
                    "side_effect_free": True,
                    "adapter": "command",
                    "command": ["python", demo_script_path],
                }
            ],
        },
        sort_keys=False,
        allow_unicode=False,
    )
    manifest[demo_script_path] = _demo_fail_rule_script()

    docs_dir_normalized = docs_dir.strip("/")
    manifest["harness/gates.yaml"] = yaml.safe_dump(
        {
            "contract_version": "1.0",
            "profiles": {
                "precommit": ["spec_validate", "demo_fail"],
                "loop_fast": ["spec_validate"],
            },
            "gates": {
                "spec_validate": _spec_validate_gate(docs_dir_normalized),
                "demo_fail": {
                    "run": (
                        "engineeringagent fitness run --format json "
                        "--manifest-path harness/fitness-functions/demo_rules.yaml"
                    )
                },
            },
        },
        sort_keys=False,
        allow_unicode=False,
    )

    return manifest


def apply_baseline_scaffold(
    project_root: Path,
    force: bool = False,
    docs_dir: str = "docs",
    profile: str = "core",
    pack: str = "slim",
    include_reviewers: bool = False,
) -> tuple[int, int]:
    """Write the init scaffold manifest to disk.

    Args:
        project_root: Repository root where scaffold files should be created.
        force: Whether to overwrite files that already exist.
        docs_dir: Docs root directory where spec files should be scaffolded.
        profile: Scaffold profile that determines language/tool defaults.
        pack: Init pack selection (slim|standard).
        include_reviewers: Backward-compatible no-op; init does not seed reviewers.

    Returns:
        Tuple of (created_count, skipped_count).
    """
    created = 0
    skipped = 0

    manifest = build_init_scaffold_manifest(
        docs_dir=docs_dir,
        profile=profile,
        pack=pack,
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
