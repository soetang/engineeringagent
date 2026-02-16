from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

import engineeringagent.loop_runtime.phases as phases_module
from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.loop_runtime.models import FeatureIterationInputs
from engineeringagent.loop_runtime.phases import (
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    run_gate_phase,
    run_reviewer_phase,
)


def _write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_run_gate_phase_fails_fast_when_checks_yaml_missing_for_run_all(
    tmp_path: Path,
) -> None:
    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    deps = GatePhaseDependencies(
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
        run_shell_command=lambda *_args, **_kwargs: SimpleNamespace(
            returncode=0,
            stdout="",
            stderr="",
        ),
    )

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "checks_config"
    assert outcome.gate_status == "failed:checks_config"


def test_run_gate_phase_reports_load_error_when_checks_document_raises(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _write_text(
        tmp_path / "harness" / "checks.yaml", "contract_version: '1.0'\nchecks: {}\n"
    )

    def boom(*_args: Any, **_kwargs: Any) -> Any:
        raise RuntimeError("kaboom")

    monkeypatch.setattr(phases_module, "load_checks_document", boom)

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )
    deps = GatePhaseDependencies(
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
        run_shell_command=lambda *_args, **_kwargs: None,
    )

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "checks_config"
    assert "kaboom" in outcome.gate_output


def test_run_reviewer_phase_forwards_request_changes_feedback_for_run_all(
    tmp_path: Path,
) -> None:
    _write_text(
        tmp_path / "harness" / "checks.yaml",
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                '    prompt_file: "harness/reviewers/prompts/doc_review.md"',
                "    when:",
                "      phase: feature_done",
                "",
            ]
        )
        + "\n",
    )
    _write_text(
        tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md",
        "Review docs.\n$responseformat\n",
    )

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    reviewer_state: dict[str, Any] = {"version": "1", "features": {}}
    deps = ReviewerPhaseDependencies(
        load_reviewer_config=lambda *_args, **_kwargs: {},
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="fallback_run_all_change_discovery_failed",
        ),
        load_reviewers_state=lambda *_args, **_kwargs: reviewer_state,
        save_reviewers_state=lambda *_args, **_kwargs: None,
        plan_reviewers=lambda *_args, **_kwargs: [],
        evaluate_cached_reviewer_approval=lambda *_args, **_kwargs: (False, ""),
        run_reviewer=lambda *_args, **_kwargs: {
            "decision": "request_changes",
            "summary": "needs work",
            "required_actions": ["fix it"],
        },
        record_reviewer_approval=lambda *_args, **_kwargs: None,
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        start_agent=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        inputs,
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml",
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "reviewer_request_changes"
    assert outcome.reviewer_status == "failed:request_changes"
    assert "needs work" in (outcome.hook_feedback or "")
