from __future__ import annotations

import json
from pathlib import Path

from engineeringagent.changed_paths import ChangedPathsResult


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def test_plan_reviewer_checks_manual_phase_marks_skip(tmp_path: Path) -> None:
    from engineeringagent.checks.reviewers.runtime import plan_reviewer_checks
    from engineeringagent.harness_checks_runtime import load_checks_document
    from engineeringagent.specs import HarnessCheckPhase

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
    doc = load_checks_document(checks_path)
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
    from engineeringagent.checks.reviewers.runtime import (
        RunPlannedReviewerChecksRequest,
        run_planned_reviewer_checks,
    )
    from engineeringagent.harness_checks_runtime import load_checks_document
    from engineeringagent.progress.paths import reviewers_state_path
    from engineeringagent.specs import HarnessCheckPhase

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
    doc = load_checks_document(checks_path)

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

    def _start_agent(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "start_agent_fn should not be called when approval is reused"
        )

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=changed_paths,
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        start_agent_fn=_start_agent,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks(request)
    assert ok
    assert failed_id is None
    assert failed_payload is None
    assert "[reviewer:doc_review] decision=approve reused=" in output


def test_run_planned_reviewer_checks_returns_ok_when_no_checks_planned(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks.reviewers.runtime import (
        RunPlannedReviewerChecksRequest,
        run_planned_reviewer_checks,
    )
    from engineeringagent.harness_checks_runtime import load_checks_document
    from engineeringagent.specs import HarnessCheckPhase

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
    doc = load_checks_document(checks_path)
    changed_paths = ChangedPathsResult(paths=(), run_all=False, reason=None)

    def _start_agent(*_args: object, **_kwargs: object) -> object:
        raise AssertionError(
            "start_agent_fn should not be called when nothing is planned"
        )

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=changed_paths,
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        start_agent_fn=_start_agent,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks(request)
    assert ok
    assert failed_id is None
    assert failed_payload is None
    assert output == ""


def test_plan_reviewer_checks_on_change_and_run_all_are_deterministic(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks.reviewers.runtime import plan_reviewer_checks
    from engineeringagent.harness_checks_runtime import load_checks_document
    from engineeringagent.specs import HarnessCheckPhase

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
    doc = load_checks_document(checks_path)

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


def test_run_planned_reviewer_checks_manual_phase_emits_skip_output(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks.reviewers.runtime import (
        RunPlannedReviewerChecksRequest,
        run_planned_reviewer_checks,
    )
    from engineeringagent.harness_checks_runtime import load_checks_document
    from engineeringagent.specs import HarnessCheckPhase

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
    doc = load_checks_document(checks_path)
    changed_paths = ChangedPathsResult(paths=(), run_all=False, reason=None)

    def _start_agent(*_args: object, **_kwargs: object) -> object:
        raise AssertionError("start_agent_fn should not be called for manual skips")

    request = RunPlannedReviewerChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=changed_paths,
        feature_id="FEAT-001",
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        start_agent_fn=_start_agent,
    )
    ok, failed_id, output, failed_payload = run_planned_reviewer_checks(request)
    assert ok
    assert failed_id is None
    assert failed_payload is None
    assert "[reviewer:doc_review] skip reason=manual" in output
