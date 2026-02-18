from __future__ import annotations

from pathlib import Path


def test_commit_subject_policy_is_harness_owned(repo_root: Path) -> None:

    policy = repo_root / "harness" / "fitness-functions" / "commit_messages.py"
    assert policy.is_file()

    validator = (
        repo_root / "harness" / "fitness-functions" / "validate_commit_messages.py"
    )
    text = validator.read_text(encoding="utf-8")
    assert "commit_messages.py" in text
    assert "engineeringagent.commit_messages" not in text

    legacy_module = repo_root / "src" / "engineeringagent" / "commit_messages.py"
    assert not legacy_module.exists(), (
        "commit subject policy must not live under src/engineeringagent"
    )
