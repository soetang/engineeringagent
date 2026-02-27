from __future__ import annotations

from pathlib import Path

from engineeringagent.checks.validate.contracts import ValidationContext, ValidationIssue

REVIEWER_PROMPTS_DIR = Path("harness") / "reviewers" / "prompts"
REVIEWER_RESPONSEFORMAT_PLACEHOLDER = "$responseformat"


class ReviewerPromptStrategyValidator:
    """Strategy-owned static validator for reviewer prompt policy."""

    strategy_type = "reviewer"
    validator_id = "reviewer.prompt-policy"

    def validate(self, *, context: ValidationContext) -> tuple[ValidationIssue, ...]:
        """Validate reviewer prompt files for deprecated static-policy tokens."""

        prompts_dir = context.project_root / REVIEWER_PROMPTS_DIR
        if not prompts_dir.exists():
            return ()

        issues: list[ValidationIssue] = []
        for prompt_path in _iter_reviewer_prompt_files(prompts_dir):
            try:
                prompt_text = prompt_path.read_text(encoding="utf-8")
            except OSError as exc:
                issues.append(
                    ValidationIssue(
                        validator_id=self.validator_id,
                        scope="strategy",
                        path=_to_repo_relative_path(context.project_root, prompt_path),
                        message=f"failed to read reviewer prompt: {exc}",
                        code="reviewer.prompt.read-failure",
                    )
                )
                continue

            if REVIEWER_RESPONSEFORMAT_PLACEHOLDER not in prompt_text:
                continue
            issues.append(
                ValidationIssue(
                    validator_id=self.validator_id,
                    scope="strategy",
                    path=_to_repo_relative_path(context.project_root, prompt_path),
                    message=(
                        "reviewer prompt must not include deprecated "
                        f"`{REVIEWER_RESPONSEFORMAT_PLACEHOLDER}`"
                    ),
                    code="reviewer.prompt.deprecated-responseformat",
                )
            )
        return tuple(issues)


def _iter_reviewer_prompt_files(reviewer_prompts_dir: Path) -> list[Path]:
    """Return reviewer prompt files in deterministic path order."""

    return sorted(reviewer_prompts_dir.glob("*.md"), key=lambda path: path.as_posix())


def _to_repo_relative_path(project_root: Path, path: Path) -> str:
    """Return repo-relative path text for stable cross-machine validate output."""

    try:
        return path.relative_to(project_root).as_posix()
    except ValueError:
        return path.as_posix()
