from __future__ import annotations

from pathlib import Path

import yaml


def test_repo_reviewers_config_excludes_removed_onboarding_reviewer(
    repo_root: Path,
) -> None:
    checks_path = repo_root / "harness" / "checks.yaml"
    document = yaml.safe_load(checks_path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)

    removed_reviewer_id = "_".join(["readme", "process"])

    checks = document.get("checks", {})
    assert removed_reviewer_id not in checks
    assert "code_simplifier" in checks
    assert checks["code_simplifier"]["type"] == "reviewer"


def test_repo_contains_only_supported_prompt_files(repo_root: Path) -> None:
    prompt_path = repo_root / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    assert prompt_path.is_file()
    assert "$responseformat" in prompt_path.read_text(encoding="utf-8")
