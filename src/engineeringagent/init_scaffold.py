from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import NamedTuple
from string import Template

import yaml

from .agents import build_backend_scaffold_manifest, default_backend_id
_SUPPORTED_SCAFFOLD_PROFILES = {"core", "python_uv"}
_SCAFFOLD_TEMPLATE_PACKAGE = "engineeringagent.scaffold_templates"
_SCAFFOLDED_USER_DOC_TEMPLATE_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("principle", "principles"),
    ("reference", "references"),
)

_SUPPORTED_INIT_PACKS = {"slim", "standard"}

DEFAULT_AGENT_MODEL = "openai/gpt-5.3-codex"


def _build_checks_yaml() -> str:
    """Build a minimal harness/checks.yaml scaffold.

    Notes:
    - The checks contract is repo-owned and is required for `engineeringagent run --all`.
    - Keep the default scaffold empty and language-agnostic.
    """

    return yaml.safe_dump(
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "checks": {},
        },
        sort_keys=False,
        allow_unicode=False,
    )


def _build_scaffold_policy_yaml(
    *,
    docs_root: str,
    user_docs: list[str],
    scaffold_docs: list[str],
    exact_sync: list[dict[str, str]],
) -> str:
    """Build a minimal scaffold policy file.

    Notes:
    - The docs allowlist fitness rule is stdlib-only and reads this file directly.
    - Keep the contract small and deterministic for reviewability.
    """

    return yaml.safe_dump(
        {
            "contract_version": "1.0",
            "docs_root": docs_root,
            "contributor_docs": [],
            "user_docs": user_docs,
            "scaffold_docs": scaffold_docs,
            "exact_sync": exact_sync,
        },
        sort_keys=False,
        allow_unicode=False,
    )


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
    return _render_template(
        package_name=_SCAFFOLD_TEMPLATE_PACKAGE,
        template_name=name,
        substitutions=substitutions,
    )


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


def _build_user_docs_manifest(
    scaffolded_user_doc_templates: tuple[tuple[str, str], ...],
) -> dict[str, str]:
    """Build scaffolded user-facing documentation files.

    Note: These are kept under the default `docs/` directory even when feature specs
    are configured to live under a separate docs root.
    """
    return {
        docs_path: _render_scaffold_template(template_name)
        for docs_path, template_name in scaffolded_user_doc_templates
    }


def _discover_scaffolded_user_doc_templates() -> tuple[tuple[str, str], ...]:
    """Discover scaffolded user docs from category-prefixed markdown templates."""
    category_roots = dict(_SCAFFOLDED_USER_DOC_TEMPLATE_CATEGORIES)
    template_root = files(_SCAFFOLD_TEMPLATE_PACKAGE)
    discovered: list[tuple[str, str]] = []

    for template_entry in sorted(template_root.iterdir(), key=lambda entry: entry.name):
        if not template_entry.is_file():
            continue

        template_name = template_entry.name
        if not template_name.endswith(".md"):
            continue

        category, _, relative_name = template_name.partition(".")
        docs_subdir = category_roots.get(category)
        if docs_subdir is None:
            continue

        discovered.append((f"docs/{docs_subdir}/{relative_name}", template_name))

    return tuple(discovered)


def _render_template(
    *,
    package_name: str,
    template_name: str,
    substitutions: dict[str, str] | None = None,
) -> str:
    """Render a template from package resources with substitutions."""
    template_text = (
        files(package_name).joinpath(template_name).read_text(encoding="utf-8")
    )
    if substitutions is None:
        return template_text
    return Template(template_text).substitute(substitutions)


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
    backend_id: str | None = None,
    agent_model: str = DEFAULT_AGENT_MODEL,
) -> dict[str, str]:
    """Build the baseline scaffold manifest for a docs root.

    Args:
        docs_dir: Docs root directory where spec files should be scaffolded.
        profile: Scaffold profile that determines language/tool defaults.
        include_reviewers: Backward-compatible no-op; init does not seed reviewers.
        backend_id: Optional backend id for backend-contributed scaffold assets.
        agent_model: Agent model id passed to backend-contributed scaffold assets.

    Returns:
        Mapping of relative file paths to scaffolded file contents.
    """
    del include_reviewers
    if profile not in _SUPPORTED_SCAFFOLD_PROFILES:
        raise ValueError(f"unsupported scaffold profile: {profile}")
    resolved_backend_id = backend_id or default_backend_id()

    docs_dir_normalized = docs_dir.strip("/")
    is_python_uv = profile == "python_uv"

    scaffolded_user_doc_templates = _discover_scaffolded_user_doc_templates()
    user_docs_manifest = _build_user_docs_manifest(scaffolded_user_doc_templates)
    policy_user_docs: list[str] = []
    policy_scaffold_docs: list[str] = []
    policy_exact_sync: list[dict[str, str]] = []
    if docs_dir_normalized == "docs":
        policy_user_docs = sorted(user_docs_manifest.keys())
        policy_scaffold_docs = list(user_docs_manifest.keys())
        policy_exact_sync = [
            {"docs_path": docs_path, "template_name": template_name}
            for docs_path, template_name in scaffolded_user_doc_templates
        ]

    manifest = {
        ".pre-commit-config.yaml": _build_precommit_config(profile=profile),
        **build_backend_scaffold_manifest(
            backend_id=resolved_backend_id,
            agent_model=agent_model,
        ),
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
        "harness/checks.yaml": _build_checks_yaml(),
        "harness/fitness-functions/rules.yaml": yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        "harness/scaffold_policy.yaml": _build_scaffold_policy_yaml(
            docs_root=docs_dir_normalized,
            user_docs=policy_user_docs,
            scaffold_docs=policy_scaffold_docs,
            exact_sync=policy_exact_sync,
        ),
        "AGENTS.md": build_scaffold_agents_markdown(),
        **user_docs_manifest,
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
    pack: str | None = None,
    options: BaselineScaffoldOptions | None = None,
) -> dict[str, str]:
    """Build init scaffold manifest for the selected pack.

    Packs:
    - slim: safe default that runs spec validation
    - standard: scaffolds an always-failing demo fitness rule for `run --all`
    """
    resolved_options = options or BaselineScaffoldOptions()
    if pack is not None:
        resolved_options = resolved_options._replace(pack=pack)

    selected_pack = resolved_options.pack
    if selected_pack not in _SUPPORTED_INIT_PACKS:
        raise ValueError(f"unsupported init pack: {selected_pack}")

    manifest = build_baseline_scaffold_manifest(
        docs_dir=resolved_options.docs_dir,
        profile=resolved_options.profile,
        include_reviewers=resolved_options.include_reviewers,
        backend_id=resolved_options.backend_id,
        agent_model=resolved_options.agent_model,
    )

    if selected_pack != "standard":
        return manifest

    demo_script_path = "harness/fitness-functions/demo_always_fail.py"
    manifest[demo_script_path] = _demo_fail_rule_script()

    manifest["harness/fitness-functions/rules.yaml"] = yaml.safe_dump(
        {
            "contract_version": "1.0",
            "rules": [
                {
                    "rule_id": "demo.always-fail",
                    "name": "Demo always failing rule",
                    "summary": "Demonstration rule that always fails.",
                    "rationale": (
                        "Provides an immediate example of a failing fitness rule "
                        "when running repo-owned checks."
                    ),
                    "remediation": (
                        "Disable the demo by removing rule_id 'demo.always-fail' "
                        "from harness/fitness-functions/rules.yaml (or re-run: engineeringagent init slim --force)."
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
    manifest["harness/checks.yaml"] = yaml.safe_dump(
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "checks": {
                "fitness_all": {"type": "fitness", "scope": "all"},
            },
        },
        sort_keys=False,
        allow_unicode=False,
    )

    return manifest


class BaselineScaffoldOptions(NamedTuple):
    """Options controlling `engineeringagent init` scaffold generation."""

    force: bool = False
    docs_dir: str = "docs"
    profile: str = "core"
    pack: str = "slim"
    include_reviewers: bool = False
    backend_id: str | None = None
    agent_model: str = DEFAULT_AGENT_MODEL


def apply_baseline_scaffold(
    project_root: Path,
    *,
    options: BaselineScaffoldOptions = BaselineScaffoldOptions(),
) -> tuple[int, int]:
    """Write the init scaffold manifest to disk.

    Args:
        project_root: Repository root where scaffold files should be created.
        options: Baseline scaffold write options.

    Returns:
        Tuple of (created_count, skipped_count).
    """
    created = 0
    skipped = 0

    manifest = build_init_scaffold_manifest(
        options=options,
    )

    for relative_path, content in manifest.items():
        target_path = project_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)

        if target_path.exists() and not options.force:
            skipped += 1
            continue

        target_path.write_text(content, encoding="utf-8")
        created += 1

    return created, skipped
