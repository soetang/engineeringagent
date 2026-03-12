from __future__ import annotations

import json
from pathlib import Path

import pytest

from engineeringagent.domain.quality import ChangedPathsResult
from engineeringagent.adapters.quality.check_strategies import strategy_run_decisions
from engineeringagent.adapters.quality.reviewers.runtime import (
    FALLBACK_REMEDIATION_GUIDANCE,
    RunPlannedReviewerChecksRequest,
    plan_reviewer_checks,
    run_planned_reviewer_checks_from_plan,
)
from engineeringagent.adapters.progress.paths import reviewers_state_path
from engineeringagent.domain.quality import (
    HarnessCheckPhase,
    HarnessChecksDocument,
    PlannedCheck,
    map_planned_checks_to_decisions,
)
from engineeringagent.domain.specification import load_yaml


def _load_checks_document(checks_path: Path):
    payload = load_yaml(checks_path)
    return HarnessChecksDocument.model_validate(payload)


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def _planned_run_decisions(
    *,
    planned: list[PlannedCheck],
    phase: HarnessCheckPhase,
):
    return strategy_run_decisions(
        map_planned_checks_to_decisions(
            entries=planned,
            check_type="reviewer",
            phase=phase,
        )
    )


def test_plan_reviewer_checks_manual_phase_marks_skip(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: manual",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)
    changed_paths = ChangedPathsResult(paths=(), run_all=False, reason=None)

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=changed_paths,
    )
    assert len(planned) == 1
    assert planned[0].check_id == "doc_review"
    assert planned[0].decision == "skip"
    assert planned[0].reason == "manual"


def test_run_planned_reviewer_checks_reuses_cached_approval(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
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
    doc = _load_checks_document(checks_path)

    state_path = reviewers_state_path(tmp_path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    state_path.write_text(
        json.dumps(
            {
                "version": "1",
                "features": {
                    "FEAT-001": {
                        "reviewers": {
                            "doc_review": {
                                "approved": True,
                                "approved_at": "2026-02-17T00:00:00Z",
                            }
                        }
                    }
                },
            },
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )

    changed_paths = ChangedPathsResult(paths=(), run_all=False, reason=None)

    def _run_agent(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "run_agent_fn should not be called when approval is reused"
        )

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=changed_paths,
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml",
        run_agent_fn=_run_agent,
    )
    planned = plan_reviewer_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks_from_plan(
        request,
        _planned_run_decisions(planned=planned, phase=request.phase),
    )
    assert ok
    assert failed_id is None
    assert failed_payload is None
    assert "[reviewer:doc_review] decision=approve reused=" in output


def test_run_planned_reviewer_checks_returns_ok_when_no_checks_planned(
    tmp_path: Path,
) -> None:
    checks_path = _write_checks_yaml(
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
    doc = _load_checks_document(checks_path)
    changed_paths = ChangedPathsResult(paths=(), run_all=False, reason=None)

    def _run_agent(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "run_agent_fn should not be called when nothing is planned"
        )

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=changed_paths,
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml",
        run_agent_fn=_run_agent,
    )
    planned = plan_reviewer_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks_from_plan(
        request,
        _planned_run_decisions(planned=planned, phase=request.phase),
    )
    assert ok
    assert failed_id is None
    assert failed_payload is None
    assert output == ""


def test_plan_reviewer_checks_on_change_and_run_all_are_deterministic(
    tmp_path: Path,
) -> None:
    checks_path = _write_checks_yaml(
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
                "      on_change:",
                "        - src/**/*.py",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(
            paths=("src/app.py",), run_all=False, reason=None
        ),
    )
    assert planned[0].decision == "run"
    assert planned[0].reason == "matched_on_change"

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason="fallback"),
    )
    assert planned[0].decision == "run"
    assert planned[0].reason == "fallback"

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(
            paths=("README.md",), run_all=False, reason=None
        ),
    )
    assert planned[0].decision == "skip"
    assert planned[0].reason == "no_on_change_match"


@pytest.mark.parametrize(
    "changed_path",
    [
        "src/engineeringagent/approach/docs/workflow.md",
        "harness/reviewers/prompts/test_reviewer.md",
        "docs/fixtures/real_opencode_hello_world_plan_template.md",
    ],
)
def test_plan_reviewer_checks_match_bundled_workflow_markdown_surfaces(
    tmp_path: Path,
    changed_path: str,
) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  intent_integrity_reviewer:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/intent_integrity_reviewer.md",
                "    when:",
                "      phase: feature_done",
                "      on_change:",
                "        - src/**/*.py",
                "        - src/engineeringagent/approach/docs/*.md",
                "        - tests/**/*.py",
                "        - harness/**/*.py",
                "        - harness/**/*.md",
                "        - docs/fixtures/**/*.md",
                "        - docs/specifications/features/**/spec.yaml",
                "        - docs/specifications/features/**/*.md",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(
            paths=(changed_path,),
            run_all=False,
            reason=None,
        ),
    )

    assert planned[0].check_id == "intent_integrity_reviewer"
    assert planned[0].decision == "run"
    assert planned[0].reason == "matched_on_change"


def test_run_planned_reviewer_checks_manual_phase_returns_empty_output(
    tmp_path: Path,
) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: manual",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)
    changed_paths = ChangedPathsResult(paths=(), run_all=False, reason=None)

    def _run_agent(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("run_agent_fn should not be called for manual skips")

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=changed_paths,
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml",
        run_agent_fn=_run_agent,
    )
    planned = plan_reviewer_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks_from_plan(
        request,
        _planned_run_decisions(planned=planned, phase=request.phase),
    )
    assert ok
    assert failed_id is None
    assert failed_payload is None
    assert output == ""


def test_run_planned_reviewer_checks_handles_non_dict_reviewer_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks_path = _write_checks_yaml(
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
    doc = _load_checks_document(checks_path)

    monkeypatch.setattr(
        "engineeringagent.adapters.quality.reviewers.runtime.run_reviewer",
        lambda *_args, **_kwargs: "invalid-payload",
        raising=True,
    )

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml",
    )
    planned = plan_reviewer_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks_from_plan(
        request,
        _planned_run_decisions(planned=planned, phase=request.phase),
    )

    assert not ok
    assert failed_id == "doc_review"
    assert "summary=(reviewer payload missing)" in output
    assert failed_payload == {
        "kind": "reviewer_feedback",
        "reviewer_id": "doc_review",
        "reviewer_phase": "feature_done",
        "decision": None,
    }


def test_run_planned_reviewer_checks_normalizes_unknown_decision_to_request_changes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks_path = _write_checks_yaml(
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
    doc = _load_checks_document(checks_path)

    monkeypatch.setattr(
        "engineeringagent.adapters.quality.reviewers.runtime.run_reviewer",
        lambda *_args, **_kwargs: {
            "decision": "not_a_real_decision",
            "summary": "needs follow-up",
            "required_actions": ["add tests"],
        },
        raising=True,
    )

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml",
    )
    planned = plan_reviewer_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks_from_plan(
        request,
        _planned_run_decisions(planned=planned, phase=request.phase),
    )

    assert not ok
    assert failed_id == "doc_review"
    assert "decision=request_changes" in output
    assert failed_payload == {
        "kind": "reviewer_feedback",
        "reviewer_id": "doc_review",
        "reviewer_phase": "feature_done",
        "decision": {
            "decision": "request_changes",
            "summary": "needs follow-up",
            "required_actions": ["add tests"],
        },
    }


def test_run_planned_reviewer_checks_verbose_output_surfaces_full_payload(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks_path = _write_checks_yaml(
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
    doc = _load_checks_document(checks_path)

    monkeypatch.setattr(
        "engineeringagent.adapters.quality.reviewers.runtime.run_reviewer",
        lambda *_args, **_kwargs: {
            "decision": "request_changes",
            "summary": "needs follow-up",
            "required_actions": ["add tests"],
            "scope_notes": "limit to touched files",
        },
        raising=True,
    )

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml",
        verbose_output=True,
    )
    planned = plan_reviewer_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks_from_plan(
        request,
        _planned_run_decisions(planned=planned, phase=request.phase),
    )

    assert not ok
    assert failed_id == "doc_review"
    assert (
        '[reviewer:doc_review] payload={"decision":"request_changes",'
        '"required_actions":["add tests"],"scope_notes":"limit to touched files",'
        '"summary":"needs follow-up"}'
    ) in output
    assert failed_payload == {
        "kind": "reviewer_feedback",
        "reviewer_id": "doc_review",
        "reviewer_phase": "feature_done",
        "decision": {
            "decision": "request_changes",
            "summary": "needs follow-up",
            "required_actions": ["add tests"],
            "scope_notes": "limit to touched files",
        },
    }


def test_run_planned_reviewer_checks_adds_fallback_remediation_when_actions_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    checks_path = _write_checks_yaml(
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
    doc = _load_checks_document(checks_path)

    monkeypatch.setattr(
        "engineeringagent.adapters.quality.reviewers.runtime.run_reviewer",
        lambda *_args, **_kwargs: {
            "decision": "request_changes",
            "summary": "needs follow-up",
            "required_actions": [],
            "scope_notes": "tests only",
        },
        raising=True,
    )

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001" / "spec.yaml",
    )
    planned = plan_reviewer_checks(
        request.doc,
        phase=request.phase,
        changed_paths=request.changed_paths,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks_from_plan(
        request,
        _planned_run_decisions(planned=planned, phase=request.phase),
    )

    assert not ok
    assert failed_id == "doc_review"
    assert (
        f"[reviewer:doc_review] remediation={FALLBACK_REMEDIATION_GUIDANCE}" in output
    )
    assert failed_payload == {
        "kind": "reviewer_feedback",
        "reviewer_id": "doc_review",
        "reviewer_phase": "feature_done",
        "decision": {
            "decision": "request_changes",
            "summary": "needs follow-up",
            "required_actions": [],
            "scope_notes": "tests only",
        },
    }
