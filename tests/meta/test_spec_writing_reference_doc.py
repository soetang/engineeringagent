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

def test_active_feature_verification_commands_do_not_require_ripgrep(
    repo_root: Path,
) -> None:
    """Ensure spec verification commands avoid ripgrep as a hard dependency."""
    features_dir = repo_root / "docs" / "spec" / "features"

    for feature_path in sorted(features_dir.glob("*.yaml")):
        body = feature_path.read_text(encoding="utf-8")
        document = yaml.safe_load(body)

        for command in _verification_commands(document):
            assert not command.strip().startswith("rg "), (
                f"{feature_path.name} uses rg: {command}"
            )
