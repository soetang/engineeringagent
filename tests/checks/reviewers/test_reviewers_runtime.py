from __future__ import annotations

from pathlib import Path
from typing import Any, cast

import pytest

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.reviewers.engine import (
    PARSER_FAILURE_SUMMARY_PREFIX,
    ReviewerDecisionEnvelope,
    ReviewerRunRequest,
    run_reviewer,
)
from engineeringagent.agents import AgentBackendError, AgentOutputValidationError

FEATURE_050_PATH = Path("docs/spec/features/FEAT-050/spec.yaml")
FEATURE_070_PATH = Path("docs/spec/features/FEAT-070/spec.yaml")
FEATURE_167_PATH = Path("docs/spec/features/FEAT-167/spec.yaml")


def test_run_reviewer_loads_harness_prompt_and_parses_decision(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        "Return strict JSON only.\n\nTEST_SENTINEL_PROMPT_INCLUDED\n",
        encoding="utf-8",
    )

    captured: dict[str, str] = {}
    captured_max_validation_retries: list[int] = []

    def _run_agent(project_root, prompt, *, output_type, max_validation_retries=2):
        captured["project_root"] = str(project_root)
        captured["prompt"] = prompt
        captured["output_type"] = str(output_type)
        captured_max_validation_retries.append(max_validation_retries)
        return ReviewerDecisionEnvelope(
            decision="approve",
            summary="No blocking issues.",
            required_actions=[],
        )

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        request=ReviewerRunRequest(
            feature_id="FEAT-050",
            feature_path=tmp_path / FEATURE_050_PATH,
            changed_paths=ChangedPathsResult(
                paths=("src/engineeringagent/checks/reviewers/engine.py",),
                run_all=False,
                reason=None,
            ),
            feedback="tighten error handling",
            run_agent_fn=_run_agent,
        ),
    )

    assert decision == {
        "decision": "approve",
        "summary": "No blocking issues.",
        "required_actions": [],
    }
    assert captured["project_root"] == str(tmp_path)
    assert "Return strict JSON only." in captured["prompt"]
    assert "JSON Schema:" not in captured["prompt"]
    assert "TEST_SENTINEL_PROMPT_INCLUDED" in captured["prompt"]
    assert captured_max_validation_retries == [2]


def test_run_reviewer_does_not_inject_deprecated_responseformat_contract(
    tmp_path,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text(
        "$responseformat\n\nTEST_SENTINEL_PROMPT_INCLUDED\n",
        encoding="utf-8",
    )

    captured: dict[str, str] = {}

    def _run_agent(_project_root, prompt, *, output_type, max_validation_retries=2):
        captured["prompt"] = prompt
        captured["output_type"] = str(output_type)
        captured["max_validation_retries"] = str(max_validation_retries)
        return ReviewerDecisionEnvelope(
            decision="approve",
            summary="No blocking issues.",
            required_actions=[],
        )

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        request=ReviewerRunRequest(
            feature_id="FEAT-050",
            feature_path=tmp_path / FEATURE_050_PATH,
            changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
            feedback=None,
            run_agent_fn=_run_agent,
        ),
    )

    assert decision["decision"] == "approve"
    assert "$responseformat" in captured["prompt"]
    assert (
        "Return exactly one strict JSON object and no other text."
        not in captured["prompt"]
    )


def test_run_reviewer_parse_failure_returns_request_changes(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Return JSON only.", encoding="utf-8")

    def _run_agent(*_args, **_kwargs):
        raise AgentOutputValidationError(
            backend="fake",
            attempts=3,
            last_text="this is not json",
            error_summary="json parse error: Expecting value",
            backend_metadata=None,
        )

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        request=ReviewerRunRequest(
            feature_id="FEAT-050",
            feature_path=tmp_path / FEATURE_050_PATH,
            changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
            feedback=None,
            run_agent_fn=_run_agent,
        ),
    )

    assert decision["decision"] == "request_changes"
    assert decision["summary"].startswith(PARSER_FAILURE_SUMMARY_PREFIX)


def test_run_reviewer_recovers_from_codex_exec_failure_by_retrying_raw_output(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Return JSON only.", encoding="utf-8")

    captured_max_validation_retries: list[int] = []

    def _run_agent(
        _project_root,
        _prompt,
        *,
        output_type,
        max_validation_retries=2,
    ):
        captured_max_validation_retries.append(max_validation_retries)
        if output_type is ReviewerDecisionEnvelope:
            raise AgentBackendError(
                backend="codex",
                message="codex exec failed",
            )
        return (
            "Execution diagnostics:\n"
            "{\n"
            '  "decision": "request_changes",\n'
            '  "summary": "Recovered JSON from raw output.",\n'
            '  "required_actions": ["address diagnostics"]\n'
            "}\n"
            "End of transcript.\n"
        )

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        request=ReviewerRunRequest(
            feature_id="FEAT-167",
            feature_path=tmp_path / FEATURE_167_PATH,
            changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
            feedback=None,
            run_agent_fn=_run_agent,
        ),
    )

    assert decision == {
        "decision": "request_changes",
        "summary": "Recovered JSON from raw output.",
        "required_actions": ["address diagnostics"],
    }
    assert captured_max_validation_retries == [2, 2]


def test_run_reviewer_passes_max_validation_retries_to_canonical_runner(
    tmp_path,
) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Return JSON only.", encoding="utf-8")

    captured: dict[str, str] = {}
    captured_max_validation_retries: list[int] = []

    def _run_agent(_project_root, _prompt, *, output_type, max_validation_retries=2):
        captured["output_type"] = str(output_type)
        captured_max_validation_retries.append(max_validation_retries)
        return ReviewerDecisionEnvelope(
            decision="approve",
            summary="Recovered on retry.",
            required_actions=[],
        )

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        request=ReviewerRunRequest(
            feature_id="FEAT-070",
            feature_path=tmp_path / FEATURE_070_PATH,
            changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
            feedback=None,
            run_agent_fn=_run_agent,
        ),
    )

    assert decision == {
        "decision": "approve",
        "summary": "Recovered on retry.",
        "required_actions": [],
    }
    assert captured_max_validation_retries == [2]


def test_run_reviewer_rejects_legacy_kwargs_invocation(tmp_path) -> None:
    legacy_kwargs_call = cast(Any, run_reviewer)
    with pytest.raises(TypeError, match="unexpected keyword argument"):
        legacy_kwargs_call(
            tmp_path,
            "code_simplifier",
            {"prompt_file": "harness/reviewers/prompts/code_simplifier.md"},
            feature_id="FEAT-050",
        )


def test_run_reviewer_does_not_require_responseformat_placeholder(tmp_path) -> None:
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True)
    prompt_path.write_text("Focus on code readability.", encoding="utf-8")

    captured: dict[str, str] = {}

    def _run_agent(_project_root, prompt, *, output_type, max_validation_retries=2):
        captured["output_type"] = str(output_type)
        captured["prompt"] = prompt
        captured["max_validation_retries"] = str(max_validation_retries)
        return ReviewerDecisionEnvelope(
            decision="approve",
            summary="Prompt without deprecated token is accepted.",
            required_actions=[],
        )

    decision = run_reviewer(
        tmp_path,
        "code_simplifier",
        {
            "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
            "trigger": {"phase": "iteration_end"},
        },
        request=ReviewerRunRequest(
            feature_id="FEAT-050",
            feature_path=tmp_path / FEATURE_050_PATH,
            changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
            feedback=None,
            run_agent_fn=_run_agent,
        ),
    )

    assert decision == {
        "decision": "approve",
        "summary": "Prompt without deprecated token is accepted.",
        "required_actions": [],
    }
    assert "Focus on code readability." in captured["prompt"]


def test_repository_code_simplifier_prompt_excludes_deprecated_responseformat_token(
    repo_root: Path,
) -> None:
    prompt_path = repo_root / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_text = prompt_path.read_text(encoding="utf-8")

    assert "$responseformat" not in prompt_text
