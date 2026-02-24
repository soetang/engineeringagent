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



