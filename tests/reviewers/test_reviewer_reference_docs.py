from __future__ import annotations

from pathlib import Path

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


def test_reviewer_reference_documents_feature_done_only_policy(repo_root: Path) -> None:
    reviewer_reference_path = (
        repo_root / "docs" / "references" / "reviewer-agents-llms.md"
    )
    body = reviewer_reference_path.read_text(encoding="utf-8")
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


def test_reviewer_authoring_guide_documents_feedback_context(repo_root: Path) -> None:
    reviewer_authoring_guide_path = (
        repo_root / "docs" / "principles" / "reviewer-authoring-guide.md"
    )
    body = reviewer_authoring_guide_path.read_text(encoding="utf-8")
    missing = [
        snippet
        for snippet in REQUIRED_FEEDBACK_CONTEXT_SNIPPETS[1:]
        if snippet not in body
    ]
    assert not missing


def test_uv_reference_documents_run_contract_guidance(repo_root: Path) -> None:
    uv_reference_path = repo_root / "docs" / "references" / "uv-llms.md"
    body = uv_reference_path.read_text(encoding="utf-8")
    removed_skip_flag = "--skip-" + "implement"
    assert removed_skip_flag not in body
    missing = [
        snippet for snippet in REQUIRED_UV_RUN_CONTRACT_SNIPPETS if snippet not in body
    ]
    assert not missing


def test_uv_reference_documents_init_profile_precommit_notes(repo_root: Path) -> None:
    uv_reference_path = repo_root / "docs" / "references" / "uv-llms.md"
    body = uv_reference_path.read_text(encoding="utf-8")
    missing = [
        snippet
        for snippet in REQUIRED_UV_INIT_PROFILE_PRECOMMIT_SNIPPETS
        if snippet not in body
    ]
    assert not missing
