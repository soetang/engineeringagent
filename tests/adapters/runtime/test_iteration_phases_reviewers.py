from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from pydantic import BaseModel

from engineeringagent.application.feature_iteration_service import (
    FeatureIterationInputs,
)
from engineeringagent.domain.quality import ChangedPathsResult
from engineeringagent.adapters.runtime.iteration_phases import (
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    run_gate_phase,
    run_reviewer_phase,
)

ACTIVE_FEATURE_PATH = Path("docs/specifications/features/FEAT-001/spec.yaml")
ARCHIVED_FEATURE_PATH = Path("docs/specifications/features_done/FEAT-001/spec.yaml")


def test_run_gate_phase_is_not_configured_without_checks_yaml(
    tmp_path: Path,
) -> None:
    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / ACTIVE_FEATURE_PATH,
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    deps = GatePhaseDependencies(
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
    )

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.gate_status == "not_configured"


def test_run_reviewer_phase_is_not_configured_without_checks_yaml(
    tmp_path: Path,
) -> None:
    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / ACTIVE_FEATURE_PATH,
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    deps = ReviewerPhaseDependencies(
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        run_agent_fn=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        inputs,
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=tmp_path / ARCHIVED_FEATURE_PATH,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.reviewer_status == "not_configured"


def test_run_reviewer_phase_runs_when_checks_yaml_exists_without_run_all(
    tmp_path: Path,
) -> None:
    (tmp_path / "harness").mkdir(parents=True, exist_ok=True)
    (tmp_path / "harness" / "checks.yaml").write_text(
        """contract_version: '1.0'
checks:
  reviewer_1:
    type: reviewer
    prompt_file: harness/reviewers/prompts/reviewer_1.md
    when:
      phase: feature_done
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "reviewer_1.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Please review.\n$responseformat\n", encoding="utf-8")

    archived_feature_path = tmp_path / ARCHIVED_FEATURE_PATH
    archived_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / ACTIVE_FEATURE_PATH,
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    start_calls: list[str] = []

    def _run_agent(
        _execution_root: Path,
        _prompt: str,
        *,
        output_type: type[BaseModel],
        backend: object = None,
        max_validation_retries: int = 2,
    ) -> BaseModel:
        del backend
        del max_validation_retries
        start_calls.append("called")
        return output_type.model_validate(
            {
                "decision": "approve",
                "summary": "ok",
                "required_actions": [],
            }
        )

    deps = ReviewerPhaseDependencies(
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=False,
            reason=None,
        ),
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        run_agent_fn=_run_agent,
    )

    outcome = run_reviewer_phase(
        inputs,
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=archived_feature_path,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.reviewer_status == "passed"
    assert start_calls == ["called"]
    assert "[reviewer:reviewer_1]" in outcome.reviewer_output


def test_run_reviewer_phase_is_not_run_when_checks_yaml_exists_but_no_feature_done_reviewers(
    tmp_path: Path,
) -> None:
    (tmp_path / "harness").mkdir(parents=True, exist_ok=True)
    (tmp_path / "harness" / "checks.yaml").write_text(
        """contract_version: '1.0'
checks:
  smoke:
    type: command
    command: echo ok
""",
        encoding="utf-8",
    )

    archived_feature_path = tmp_path / ARCHIVED_FEATURE_PATH
    archived_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / ACTIVE_FEATURE_PATH,
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    deps = ReviewerPhaseDependencies(
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=False,
            reason=None,
        ),
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        run_agent_fn=lambda *_args, **_kwargs: (_ for _ in ()).throw(
            AssertionError("start_agent should not be called")
        ),
    )

    outcome = run_reviewer_phase(
        inputs,
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=archived_feature_path,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.reviewer_status == "not_run"
    assert outcome.reviewer_output == ""


def test_run_reviewer_phase_marks_archive_rollback_after_failure(
    tmp_path: Path,
    monkeypatch,
) -> None:
    (tmp_path / "harness").mkdir(parents=True, exist_ok=True)
    (tmp_path / "harness" / "checks.yaml").write_text(
        """contract_version: '1.0'
checks:
  reviewer_1:
    type: reviewer
    prompt_file: harness/reviewers/prompts/reviewer_1.md
    when:
      phase: feature_done
""",
        encoding="utf-8",
    )

    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "reviewer_1.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Please review.\n$responseformat\n", encoding="utf-8")

    archived_feature_path = tmp_path / ARCHIVED_FEATURE_PATH
    archived_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / ACTIVE_FEATURE_PATH,
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    monkeypatch.setattr(
        "engineeringagent.adapters.runtime.iteration_phases.run_checks",
        lambda *_args, **_kwargs: SimpleNamespace(
            ok=False,
            dry_run=False,
            failed_check_id="reviewer_1",
            output="[reviewer:reviewer_1] decision=request_changes",
            prompt_feedback="reviewer feedback",
        ),
    )

    restore_calls: list[tuple[Path, Path]] = []
    deps = ReviewerPhaseDependencies(
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=False,
            reason=None,
        ),
        restore_archived_feature=lambda archived_path, feature_path: (
            restore_calls.append((archived_path, feature_path)) or True,
            "",
        ),
        run_agent_fn=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        inputs,
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=archived_feature_path,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.archived_rolled_back is True
    assert restore_calls == [(archived_feature_path, inputs.feature_path)]
