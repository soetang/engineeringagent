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


def _resolve_docs_path(docs_root: Path, docs_path: Path) -> Path:
    if docs_path == docs_root or docs_root in docs_path.parents:
        return docs_path
    return docs_root / docs_path


def test_scaffold_policy_exact_sync_docs_match_scaffold_templates(
    repo_root: Path,
) -> None:
    """Require every scaffold policy exact_sync pair to be byte-identical."""
    policy_path = repo_root / "harness" / "scaffold_policy.yaml"
    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))

    assert isinstance(payload, dict)
    docs_root_raw = payload.get("docs_root")
    docs_root = Path(docs_root_raw) if isinstance(docs_root_raw, str) else Path("docs")

    exact_sync = payload.get("exact_sync")
    assert isinstance(exact_sync, list)
    assert exact_sync

    for entry in exact_sync:
        assert isinstance(entry, dict)
        docs_path = entry.get("docs_path")
        template_name = entry.get("template_name")
        assert isinstance(docs_path, str)
        assert isinstance(template_name, str)

        canonical_relative = _resolve_docs_path(docs_root, Path(docs_path))
        canonical_path = repo_root / canonical_relative
        template_path = (
            repo_root
            / "src"
            / "engineeringagent"
            / "scaffold_templates"
            / template_name
        )
        assert canonical_path.exists(), (
            f"exact_sync missing canonical docs: docs='{canonical_relative}' "
            f"template='src/engineeringagent/scaffold_templates/{template_name}'"
        )
        assert template_path.exists(), (
            "exact_sync missing scaffold template: "
            f"docs='{canonical_relative}' "
            f"template='src/engineeringagent/scaffold_templates/{template_name}'"
        )
        assert canonical_path.read_bytes() == template_path.read_bytes(), (
            f"exact_sync mismatch: docs='{canonical_relative}' "
            f"template='src/engineeringagent/scaffold_templates/{template_name}'"
        )


def test_active_feature_specs_do_not_reference_implement_command(
    repo_root: Path,
) -> None:
    """Reject stale references to deprecated --implement-command usage."""
    features_dir = repo_root / "docs" / "spec" / "features"

    for feature_path in sorted(features_dir.glob("*.yaml")):
        body = feature_path.read_text(encoding="utf-8")
        assert "--implement-command" not in body


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
