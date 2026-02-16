from __future__ import annotations

from pathlib import Path

import yaml


def _verification_commands(document: dict) -> list[str]:
    commands: list[str] = []
    for subtask in document.get("subtasks", []):
        for command in subtask.get("verification", []):
            if isinstance(command, str):
                commands.append(command)
    return commands


def test_spec_writing_reference_uses_supported_validate_command(
    repo_root: Path,
) -> None:
    canonical_path = repo_root / "docs" / "references" / "spec-writing-llms.md"
    body = canonical_path.read_text(encoding="utf-8")

    assert "scripts/validate_specs.py" not in body
    assert "engineeringagent validate" in body


def test_spec_writing_reference_is_exact_sync_with_scaffold_template(
    repo_root: Path,
) -> None:
    canonical_path = repo_root / "docs" / "references" / "spec-writing-llms.md"
    template_path = (
        repo_root
        / "src"
        / "engineeringagent"
        / "scaffold_templates"
        / "reference.spec-writing-llms.md"
    )
    assert canonical_path.read_bytes() == template_path.read_bytes()


def test_active_feature_specs_do_not_reference_implement_command(
    repo_root: Path,
) -> None:
    features_dir = repo_root / "docs" / "spec" / "features"

    for feature_path in sorted(features_dir.glob("*.yaml")):
        body = feature_path.read_text(encoding="utf-8")
        assert "--implement-command" not in body


def test_active_feature_verification_commands_do_not_require_ripgrep(
    repo_root: Path,
) -> None:
    features_dir = repo_root / "docs" / "spec" / "features"

    for feature_path in sorted(features_dir.glob("*.yaml")):
        body = feature_path.read_text(encoding="utf-8")
        document = yaml.safe_load(body)

        for command in _verification_commands(document):
            assert not command.strip().startswith("rg "), (
                f"{feature_path.name} uses rg: {command}"
            )
