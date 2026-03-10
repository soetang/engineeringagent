from __future__ import annotations

from pathlib import Path


def test_reviewer_prompts_reference_bundled_feature_packages(repo_root: Path) -> None:
    prompt_paths = [
        repo_root / "harness" / "reviewers" / "prompts" / "test_reviewer.md",
        repo_root
        / "harness"
        / "reviewers"
        / "prompts"
        / "intent_integrity_reviewer.md",
    ]

    for prompt_path in prompt_paths:
        prompt = prompt_path.read_text(encoding="utf-8")

        assert "docs/spec/features/**/spec.yaml" in prompt
        assert "legacy wrappers (`docs/spec/features/*.yaml`)" in prompt
        assert "`plan.md` phases" in prompt or "plan.md phases" in prompt
        assert "`planning_tier`" in prompt or "planning_tier" in prompt
        assert "`research.md`" in prompt or "research.md" in prompt
        assert "supporting artifacts" in prompt or "support files" in prompt
        assert "compatibility wrapper" in prompt
        assert "canonical bundled package" in prompt
