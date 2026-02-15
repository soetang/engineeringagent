from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEWER_REFERENCE_PATH = REPO_ROOT / "docs" / "references" / "reviewer-agents-llms.md"
REQUIRED_POLICY_SNIPPETS = (
    "Runtime executes reviewers only at `feature_done`.",
    "`trigger.phase: iteration_end` is treated as a compatibility alias and normalized to `feature_done`.",
    "All reviewer decisions (`approve`, `warning`, `request_changes`) produce forwarded feedback for the next implement pass.",
    "Any forwarded reviewer feedback requires exactly one follow-up implement pass before completion commit eligibility.",
    "`reviewer_feedback_present`",
    "`reviewer_feedback_summary`",
    "`reviewer_feedback_forwarded_begin`",
    "`reviewer_feedback_forwarded_end`",
    "Reviewer execution prefers OpenCode JSON event output via `opencode run --format json`.",
    "If the decision payload fails JSON parsing or schema validation, the runner retries up to 2 times in the same OpenCode session.",
    "The `$responseformat` placeholder expands to a contract that includes the reviewer decision envelope JSON Schema.",
)

REQUIRED_SANDBOX_SNIPPETS = (
    "`sandbox.mode`: currently",
    "`clean_room_readme_cli`",
    "`sandbox.assets`",
)


def test_reviewer_reference_documents_feature_done_only_policy() -> None:
    body = REVIEWER_REFERENCE_PATH.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_POLICY_SNIPPETS if snippet not in body]
    missing.extend(
        [snippet for snippet in REQUIRED_SANDBOX_SNIPPETS if snippet not in body]
    )

    assert not missing
