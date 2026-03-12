from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from string import Template

import yaml

from ..adapters.agents import build_backend_scaffold_manifest, default_backend_id
from ..ports.init_workspace import BaselineScaffoldOptions, DEFAULT_AGENT_MODEL

_SCAFFOLD_TEMPLATE_PACKAGE = "engineeringagent.scaffold_templates"
_SUPPORTED_INIT_PACKS = {"slim", "standard"}
_PRECOMMIT_TEMPLATES = {
    "core": "precommit.core.yaml",
    "python_uv": "precommit.python_uv.yaml",
}
_SUPPORTED_SCAFFOLD_PROFILES = frozenset(_PRECOMMIT_TEMPLATES)
DEFAULT_AGENTS_LAUNCHER = "uvx"
AGENTS_LAUNCHER_CHOICES: tuple[str, ...] = ("uvx", "uv-run", "engineeringagent")
AGENTS_LAUNCHER_COMMANDS = {
    "uvx": "uvx engineeringagent ...",
    "uv-run": "uv run engineeringagent ...",
    "engineeringagent": "engineeringagent ...",
}


def _build_checks_yaml() -> str:
    """Build a minimal harness/checks.yaml scaffold."""

    return yaml.safe_dump(
        {
            "contract_version": "1.0",
            "defaults": {"when": {"phase": "iteration_end"}},
            "groups": [],
            "checks": {},
        },
        sort_keys=False,
        allow_unicode=False,
    )


def _spec_validate_gate(docs_dir_normalized: str) -> dict[str, object]:
    """Return a stable spec validation gate config for harness profiles."""

    return {
        "run": "engineeringagent validate",
        "on_change": [
            f"{docs_dir_normalized}/specifications/**/*.yaml",
            f"{docs_dir_normalized}/specifications/**/*.yml",
            f"{docs_dir_normalized}/specifications/**/*.json",
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
    template_name = _PRECOMMIT_TEMPLATES.get(profile)
    if template_name is None:
        raise ValueError(f"unsupported scaffold profile: {profile}")

    return _render_scaffold_template(template_name)


def build_scaffold_agents_markdown(
    agents_launcher: str = DEFAULT_AGENTS_LAUNCHER,
) -> str:
    """Build baseline AGENTS.md guidance for scaffolded repositories."""
    launcher_command = AGENTS_LAUNCHER_COMMANDS.get(agents_launcher)
    if launcher_command is None:
        choices = ", ".join(AGENTS_LAUNCHER_CHOICES)
        raise ValueError(
            f"unsupported AGENTS launcher: {agents_launcher} (expected one of: {choices})"
        )

    rendered = _render_scaffold_template("AGENTS.md")
    if agents_launcher == DEFAULT_AGENTS_LAUNCHER:
        return rendered
    default_command = AGENTS_LAUNCHER_COMMANDS[DEFAULT_AGENTS_LAUNCHER]
    return rendered.replace(f"`{default_command}`", f"`{launcher_command}`")


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
    """Build follow-up feature spec content for AGENTS merge work."""
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
    backend_id: str | None = None,
    agents_launcher: str = DEFAULT_AGENTS_LAUNCHER,
    agent_model: str = DEFAULT_AGENT_MODEL,
) -> dict[str, str]:
    """Build the baseline scaffold manifest for a docs root."""
    if profile not in _SUPPORTED_SCAFFOLD_PROFILES:
        raise ValueError(f"unsupported scaffold profile: {profile}")
    resolved_backend_id = backend_id or default_backend_id()

    docs_dir_normalized = docs_dir.strip("/")
    is_python_uv = profile == "python_uv"

    manifest = {
        ".pre-commit-config.yaml": _build_precommit_config(profile=profile),
        **build_backend_scaffold_manifest(
            backend_id=resolved_backend_id,
            agent_model=agent_model,
        ),
        f"{docs_dir_normalized}/specifications/features/.gitkeep": "",
        f"{docs_dir_normalized}/specifications/features_done/.gitkeep": "",
        "harness/checks.yaml": _build_checks_yaml(),
        "harness/fitness_functions/rules.yaml": yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        "AGENTS.md": build_scaffold_agents_markdown(agents_launcher),
    }

    if is_python_uv:
        manifest["harness/fitness_functions/validate_commit_messages.py"] = (
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
    """Build init scaffold manifest for the selected pack."""
    resolved_options = options or BaselineScaffoldOptions()
    if pack is not None:
        resolved_options = resolved_options._replace(pack=pack)

    selected_pack = resolved_options.pack
    if selected_pack not in _SUPPORTED_INIT_PACKS:
        raise ValueError(f"unsupported init pack: {selected_pack}")

    manifest = build_baseline_scaffold_manifest(
        docs_dir=resolved_options.docs_dir,
        profile=resolved_options.profile,
        backend_id=resolved_options.backend_id,
        agents_launcher=resolved_options.agents_launcher,
        agent_model=resolved_options.agent_model,
    )

    if selected_pack != "standard":
        return manifest

    demo_script_path = "harness/fitness_functions/demo_always_fail.py"
    manifest[demo_script_path] = _demo_fail_rule_script()

    manifest["harness/fitness_functions/rules.yaml"] = yaml.safe_dump(
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
                        "from harness/fitness_functions/rules.yaml (or re-run: engineeringagent init slim --force)."
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
            "groups": [
                {
                    "group_id": "fitness",
                    "description": "Run all configured fitness functions.",
                    "checks": ["fitness_all"],
                }
            ],
            "checks": {
                "fitness_all": {"type": "fitness", "scope": "all"},
            },
        },
        sort_keys=False,
        allow_unicode=False,
    )

    return manifest


def apply_baseline_scaffold(
    project_root: Path,
    *,
    options: BaselineScaffoldOptions = BaselineScaffoldOptions(),
) -> tuple[int, int]:
    """Write the init scaffold manifest to disk."""
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
