from __future__ import annotations

from pathlib import Path

from engineeringagent.checks.reviewers.validator import ReviewerPromptStrategyValidator
from engineeringagent.checks.validate.contracts import ValidationContext


def _context(project_root: Path) -> ValidationContext:
    return ValidationContext(
        project_root=project_root,
        docs_root=project_root / "docs",
        schema_only=False,
    )


def test_reviewer_strategy_validator_reports_deprecated_responseformat(
    tmp_path: Path,
) -> None:
    prompts_dir = tmp_path / "harness" / "reviewers" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    prompt_path = prompts_dir / "deprecated.md"
    prompt_path.write_text("$responseformat\n", encoding="utf-8")

    issues = ReviewerPromptStrategyValidator().validate(context=_context(tmp_path))

    assert len(issues) == 1
    assert issues[0].validator_id == "reviewer.prompt-policy"
    assert issues[0].scope == "strategy"
    assert issues[0].path == "harness/reviewers/prompts/deprecated.md"
    assert issues[0].code == "reviewer.prompt.deprecated-responseformat"


def test_reviewer_strategy_validator_ignores_prompts_without_deprecated_token(
    tmp_path: Path,
) -> None:
    prompts_dir = tmp_path / "harness" / "reviewers" / "prompts"
    prompts_dir.mkdir(parents=True, exist_ok=True)
    (prompts_dir / "ok.md").write_text("Return strict JSON.\n", encoding="utf-8")

    issues = ReviewerPromptStrategyValidator().validate(context=_context(tmp_path))

    assert issues == ()
