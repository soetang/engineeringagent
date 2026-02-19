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

    assert "test_reviewer" in checks
    assert checks["test_reviewer"]["type"] == "reviewer"
    assert (
        checks["test_reviewer"]["prompt_file"]
        == "harness/reviewers/prompts/test_reviewer.md"
    )
    assert checks["test_reviewer"]["when"]["phase"] == "feature_done"
    assert checks["test_reviewer"]["when"]["on_change"] == ["tests/**/*.py"]


def test_repo_contains_only_supported_prompt_files(repo_root: Path) -> None:
    prompt_path = repo_root / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    assert prompt_path.is_file()
    assert "$responseformat" not in prompt_path.read_text(encoding="utf-8")

    prompt_path = repo_root / "harness" / "reviewers" / "prompts" / "test_reviewer.md"
    assert prompt_path.is_file()
    assert "$responseformat" not in prompt_path.read_text(encoding="utf-8")


def test_reviewer_docs_do_not_reference_deprecated_responseformat_token(
    repo_root: Path,
) -> None:
    paths = [
        repo_root / "docs" / "references" / "reviewer-authoring-guide.md",
        repo_root / "docs" / "references" / "reviewer-agents.md",
    ]
    for path in paths:
        body = path.read_text(encoding="utf-8")
        assert "$responseformat" not in body, (
            f"{path} must not mention deprecated token"
        )
