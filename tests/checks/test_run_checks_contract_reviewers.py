from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel

from engineeringagent.checks import run_checks
from engineeringagent.checks.reviewers.runtime import FALLBACK_REMEDIATION_GUIDANCE

from tests.checks.run_checks_contract_support import write_reviewer_fixture


def test_run_checks_reviewers_returns_not_implemented_result(tmp_path: Path) -> None:
    feature_path = write_reviewer_fixture(tmp_path)
    calls: list[tuple[Path, str]] = []

    def run_agent(
        execution_root: Path,
        prompt: str,
        *,
        output_type: type[BaseModel],
        backend: object = None,
        max_validation_retries: int = 2,
    ) -> BaseModel:
        del backend
        del max_validation_retries
        calls.append((execution_root, prompt))
        return output_type.model_validate(
            {
                "decision": "approve",
                "summary": "ok",
                "required_actions": [],
            }
        )

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        run_agent_fn=run_agent,
    )

    assert result.ok
    assert result.failed_check_id is None
    assert [decision["check_id"] for decision in result.decisions] == ["doc_review"]
    assert [record.check_id for record in result.executions] == ["doc_review"]
    assert len(calls) == 1


def test_run_checks_reviewers_request_changes_fails_deterministically(
    tmp_path: Path,
) -> None:
    feature_path = write_reviewer_fixture(tmp_path)

    def run_agent(
        _execution_root: Path,
        _prompt: str,
        *,
        output_type: type[BaseModel],
        backend: object = None,
        max_validation_retries: int = 2,
    ) -> BaseModel:
        del backend
        del max_validation_retries
        return output_type.model_validate(
            {
                "decision": "request_changes",
                "summary": "nope",
                "required_actions": ["fix"],
            }
        )

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        run_agent_fn=run_agent,
    )

    assert not result.ok
    assert result.failed_check_id == "doc_review"
    assert [decision["check_id"] for decision in result.decisions] == ["doc_review"]
    assert [record.check_id for record in result.executions] == ["doc_review"]


def test_run_checks_reviewers_verbose_output_surfaces_full_payload(
    tmp_path: Path,
) -> None:
    feature_path = write_reviewer_fixture(tmp_path)

    def run_agent(
        _execution_root: Path,
        _prompt: str,
        *,
        output_type: type[BaseModel],
        backend: object = None,
        max_validation_retries: int = 2,
    ) -> BaseModel:
        del backend
        del max_validation_retries
        return output_type.model_validate(
            {
                "decision": "request_changes",
                "summary": "needs follow-up",
                "required_actions": ["fix"],
                "scope_notes": "tests only",
            }
        )

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        verbose_output=True,
        run_agent_fn=run_agent,
    )

    assert not result.ok
    assert (
        '[reviewer:doc_review] payload={"decision":"request_changes",'
        '"required_actions":["fix"],"scope_notes":"tests only",'
        '"summary":"needs follow-up"}'
    ) in result.output


def test_run_checks_reviewers_adds_fallback_remediation_when_actions_missing(
    tmp_path: Path,
) -> None:
    feature_path = write_reviewer_fixture(tmp_path)

    def run_agent(
        _execution_root: Path,
        _prompt: str,
        *,
        output_type: type[BaseModel],
        backend: object = None,
        max_validation_retries: int = 2,
    ) -> BaseModel:
        del backend
        del max_validation_retries
        return output_type.model_validate(
            {
                "decision": "request_changes",
                "summary": "needs follow-up",
                "required_actions": [],
                "scope_notes": "tests only",
            }
        )

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        run_agent_fn=run_agent,
    )

    assert not result.ok
    assert f"[reviewer:doc_review] remediation={FALLBACK_REMEDIATION_GUIDANCE}" in result.output
    assert result.prompt_feedback is not None


def test_run_checks_reviewers_treats_blank_actions_as_missing_for_prompt_feedback(
    tmp_path: Path,
) -> None:
    feature_path = write_reviewer_fixture(tmp_path)

    def run_agent(
        _execution_root: Path,
        _prompt: str,
        *,
        output_type: type[BaseModel],
        backend: object = None,
        max_validation_retries: int = 2,
    ) -> BaseModel:
        del backend
        del max_validation_retries
        return output_type.model_validate(
            {
                "decision": "request_changes",
                "summary": "needs follow-up",
                "required_actions": [" ", "\t", ""],
                "scope_notes": "tests only",
            }
        )

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        run_agent_fn=run_agent,
    )

    assert not result.ok
    assert f"[reviewer:doc_review] remediation={FALLBACK_REMEDIATION_GUIDANCE}" in result.output
    assert result.prompt_feedback is not None
