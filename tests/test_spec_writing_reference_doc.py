from __future__ import annotations

from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[1]
CANONICAL_PATH = REPO_ROOT / "docs" / "references" / "spec-writing-llms.md"
TEMPLATE_PATH = (
    REPO_ROOT
    / "src"
    / "engineeringagent"
    / "scaffold_templates"
    / "reference.spec-writing-llms.md"
)


def _verification_commands(document: dict) -> list[str]:
    commands: list[str] = []
    for subtask in document.get("subtasks", []):
        for command in subtask.get("verification", []):
            if isinstance(command, str):
                commands.append(command)
    return commands


def test_spec_writing_reference_uses_supported_validate_command() -> None:
    body = CANONICAL_PATH.read_text(encoding="utf-8")

    assert "scripts/validate_specs.py" not in body
    assert "engineeringagent validate" in body


def test_spec_writing_reference_is_exact_sync_with_scaffold_template() -> None:
    assert CANONICAL_PATH.read_bytes() == TEMPLATE_PATH.read_bytes()


def test_active_feature_specs_do_not_reference_implement_command() -> None:
    features_dir = REPO_ROOT / "docs" / "spec" / "features"

    for feature_path in sorted(features_dir.glob("*.yaml")):
        body = feature_path.read_text(encoding="utf-8")
        assert "--implement-command" not in body


def test_active_feature_verification_commands_do_not_require_ripgrep() -> None:
    features_dir = REPO_ROOT / "docs" / "spec" / "features"

    for feature_path in sorted(features_dir.glob("*.yaml")):
        body = feature_path.read_text(encoding="utf-8")
        document = yaml.safe_load(body)

        for command in _verification_commands(document):
            assert not command.strip().startswith("rg "), (
                f"{feature_path.name} uses rg: {command}"
            )
