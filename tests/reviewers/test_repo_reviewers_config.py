from __future__ import annotations

from pathlib import Path

import yaml


def test_repo_reviewers_config_excludes_removed_onboarding_reviewer(
    repo_root: Path,
) -> None:
    reviewers_path = repo_root / "harness" / "reviewers.yaml"
    document = yaml.safe_load(reviewers_path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)

    removed_reviewer_id = "_".join(["readme", "process"])

    profiles = document.get("profiles", {})
    assert removed_reviewer_id not in profiles.get("loop_fast", [])

    reviewers = document.get("reviewers", {})
    assert removed_reviewer_id not in reviewers
    assert "code_simplifier" in reviewers


def test_repo_contains_only_supported_prompt_files(repo_root: Path) -> None:
    prompt_path = repo_root / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    assert prompt_path.is_file()
    assert "$responseformat" in prompt_path.read_text(encoding="utf-8")
