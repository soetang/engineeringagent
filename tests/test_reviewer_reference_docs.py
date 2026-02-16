from __future__ import annotations

from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
REVIEWER_REFERENCE_PATH = REPO_ROOT / "docs" / "references" / "reviewer-agents-llms.md"
REVIEWER_AUTHORING_GUIDE_PATH = (
    REPO_ROOT / "docs" / "principles" / "reviewer-authoring-guide.md"
)
UV_REFERENCE_PATH = REPO_ROOT / "docs" / "references" / "uv-llms.md"
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


REQUIRED_FEEDBACK_CONTEXT_SNIPPETS = (
    "`feedback_context`: optional string forwarded verbatim into the next implement pass feedback when a follow-up implement pass is required.",
    "`feedback_context`: optional string forwarded verbatim alongside reviewer feedback into the next implement pass.",
)


REQUIRED_UV_RUN_CONTRACT_SNIPPETS = (
    "uv run python -m engineeringagent.cli gates run --profile loop_fast",
    "uv run python -m engineeringagent.cli run --all --dry-run",
)


REQUIRED_UV_INIT_PROFILE_PRECOMMIT_SNIPPETS = (
    "Init scaffold profile notes (slim pack)",
    "`core`: the `precommit` profile runs `spec_validate` only.",
    "`python_uv`: the `precommit` profile runs `spec_validate` + `ruff_validate`.",
    "Ruff gate command (isolated): `uvx ruff check --isolated .`",
    "No Pyright gate is scaffolded for `python_uv`.",
)


def test_reviewer_reference_documents_feature_done_only_policy() -> None:
    body = REVIEWER_REFERENCE_PATH.read_text(encoding="utf-8")
    missing = [snippet for snippet in REQUIRED_POLICY_SNIPPETS if snippet not in body]
    missing.extend(
        [snippet for snippet in REQUIRED_SANDBOX_SNIPPETS if snippet not in body]
    )
    missing.extend(
        [
            snippet
            for snippet in REQUIRED_FEEDBACK_CONTEXT_SNIPPETS[:1]
            if snippet not in body
        ]
    )

    assert not missing


def test_reviewer_authoring_guide_documents_feedback_context() -> None:
    body = REVIEWER_AUTHORING_GUIDE_PATH.read_text(encoding="utf-8")
    missing = [
        snippet
        for snippet in REQUIRED_FEEDBACK_CONTEXT_SNIPPETS[1:]
        if snippet not in body
    ]
    assert not missing


def test_uv_reference_documents_run_contract_guidance() -> None:
    body = UV_REFERENCE_PATH.read_text(encoding="utf-8")
    removed_skip_flag = "--skip-" + "implement"
    assert removed_skip_flag not in body
    missing = [
        snippet for snippet in REQUIRED_UV_RUN_CONTRACT_SNIPPETS if snippet not in body
    ]
    assert not missing


def test_uv_reference_documents_init_profile_precommit_notes() -> None:
    body = UV_REFERENCE_PATH.read_text(encoding="utf-8")
    missing = [
        snippet
        for snippet in REQUIRED_UV_INIT_PROFILE_PRECOMMIT_SNIPPETS
        if snippet not in body
    ]
    assert not missing
