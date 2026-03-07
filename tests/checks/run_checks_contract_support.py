from __future__ import annotations

from pathlib import Path
from typing import Any


def write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def write_reviewer_fixture(tmp_path: Path) -> Path:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Please review. $responseformat\n", encoding="utf-8")

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )
    return feature_path


class StubStrategy:
    def __init__(self, check_type: str) -> None:
        self.check_type = check_type

    def plan(self, *, context: Any) -> tuple[Any, ...]:
        _ = context
        return ()

    def execute(self, *, context: Any, decisions: tuple[Any, ...]) -> tuple[Any, ...]:
        _ = (context, decisions)
        return ()

    def render_prompt_feedback(self, *, failed_record: Any) -> str | None:
        _ = failed_record
        return None
