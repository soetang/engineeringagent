from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel

from engineeringagent.adapters.quality.command_checks import CommandInvocationRecord
from engineeringagent.adapters.runtime.iteration_phases import (
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    run_gate_phase,
    run_reviewer_phase,
)
from engineeringagent.application.feature_iteration import FeatureIterationInputs
from engineeringagent.checks import ChecksRunResult
from engineeringagent.domain.quality import ChangedPathsResult


ACTIVE_FEATURE_PATH = Path("docs/specifications/features/FEAT-001/spec.yaml")
ARCHIVED_FEATURE_PATH = Path("docs/specifications/features_done/FEAT-001/spec.yaml")


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def _write_fitness_manifest(tmp_path: Path, content: str) -> Path:
    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(content, encoding="utf-8")
    return manifest_path


def _feature_iteration_inputs(tmp_path: Path) -> FeatureIterationInputs:
    return FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / ACTIVE_FEATURE_PATH,
        run_all=True,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )


def _gate_dependencies(
    changed_paths: ChangedPathsResult,
) -> GatePhaseDependencies:
    return GatePhaseDependencies(
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        collect_changed_paths=lambda *_args, **_kwargs: changed_paths,
    )


def test_run_gate_phase_uses_checks_yaml_for_run_all_iteration_end(
    tmp_path: Path,
) -> None:
    """Run iteration-end gate checks from the harness checks catalog."""
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \'print(\\"ok\\")\'"',
                "",
            ]
        ),
    )

    outcome = run_gate_phase(
        _feature_iteration_inputs(tmp_path),
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_gate_dependencies(
            ChangedPathsResult(paths=(), run_all=True, reason=None)
        ),
    )

    assert outcome.result == "passed"
    assert outcome.gate_status == "passed"
    assert "[check:smoke]" in outcome.gate_output


def test_run_gate_phase_skips_on_change_command_checks_when_no_match(
    tmp_path: Path,
) -> None:
    """Report a skip decision when no changed path matches an on-change command."""
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  ruff:",
                "    type: command",
                "    command: echo should-not-run",
                "    when:",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )

    outcome = run_gate_phase(
        _feature_iteration_inputs(tmp_path),
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_gate_dependencies(
            ChangedPathsResult(paths=("README.md",), run_all=False, reason=None)
        ),
    )

    assert outcome.result == "passed"
    assert (
        "[decision:ruff] type=command phase=iteration_end decision=skip"
        in outcome.gate_output
    )
    assert "reason=no_on_change_match" in outcome.gate_output


def test_run_gate_phase_runs_feature_done_checks_only_when_archived(
    tmp_path: Path,
) -> None:
    """Only execute feature-done command checks once the feature was archived."""
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  iter:",
                "    type: command",
                "    command: echo iter",
                "  done:",
                "    type: command",
                "    command: echo done",
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )

    dependencies = _gate_dependencies(
        ChangedPathsResult(paths=(), run_all=True, reason=None)
    )

    iteration_outcome = run_gate_phase(
        _feature_iteration_inputs(tmp_path),
        archived_in_iteration=False,
        archived_path=None,
        dependencies=dependencies,
    )
    assert "[check:iter] command=echo iter" in iteration_outcome.gate_output
    assert "[check:done] command=echo done" not in iteration_outcome.gate_output

    feature_done_outcome = run_gate_phase(
        _feature_iteration_inputs(tmp_path),
        archived_in_iteration=True,
        archived_path=tmp_path / ARCHIVED_FEATURE_PATH,
        dependencies=dependencies,
    )
    assert "[check:iter] command=echo iter" in feature_done_outcome.gate_output
    assert "[check:done] command=echo done" in feature_done_outcome.gate_output


def test_run_gate_phase_uses_structured_invocations_for_gate_timings(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    """Map structured command-invocation records into gate timing telemetry."""
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo smoke",
                "",
            ]
        ),
    )

    def _fake_run_checks(*_args: Any, **_kwargs: Any) -> ChecksRunResult:
        return ChecksRunResult(
            ok=True,
            output="command ran without legacy check prefix",
            command_invocations=(
                CommandInvocationRecord(
                    check_id="smoke",
                    command="echo smoke",
                    returncode=0,
                    started_epoch_sec=10,
                    ended_epoch_sec=13,
                    started_monotonic_ns=100,
                    finished_monotonic_ns=200,
                    duration_ms=3.0,
                ),
            ),
        )

    monkeypatch.setattr(
        "engineeringagent.adapters.runtime.iteration_phases.run_checks", _fake_run_checks
    )

    outcome = run_gate_phase(
        _feature_iteration_inputs(tmp_path),
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_gate_dependencies(
            ChangedPathsResult(paths=(), run_all=True, reason=None)
        ),
    )

    assert outcome.result == "passed"
    assert len(outcome.command_timings) == 1
    assert outcome.command_timings[0].gate == "smoke"
    assert outcome.command_timings[0].command == "echo smoke"
    assert outcome.command_timings[0].started_at == "1970-01-01T00:00:10Z"
    assert outcome.command_timings[0].ended_at == "1970-01-01T00:00:13Z"
    assert outcome.command_timings[0].duration_sec == 3


def test_run_gate_phase_runs_fitness_checks_scope_all(
    tmp_path: Path,
) -> None:
    """Execute scope-all fitness checks as part of the gate phase."""
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_all:",
                "    type: fitness",
                "    scope: all",
                "",
            ]
        ),
    )
    _write_fitness_manifest(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: demo.pass",
                "    name: Demo",
                "    summary: Demo pass",
                "    rationale: Demo rationale",
                "    remediation: Demo remediation",
                "    scope: repo",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                "      - >-",
                '        import json; print(json.dumps({"contract_version": "1.0", "rule_id": "demo.pass", "status": "pass", "severity": "warning", "summary": "ok", "violations": []}))',
                "",
            ]
        ),
    )

    outcome = run_gate_phase(
        _feature_iteration_inputs(tmp_path),
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_gate_dependencies(
            ChangedPathsResult(paths=(), run_all=True, reason=None)
        ),
    )

    assert outcome.result == "passed"
    assert "[check:fitness_all]" in outcome.gate_output
    assert "[fitness:demo.pass] status=pass" in outcome.gate_output


def test_run_gate_phase_fails_when_fitness_check_fails(
    tmp_path: Path,
) -> None:
    """Fail the gate phase when a fitness rule reports failure."""
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_all:",
                "    type: fitness",
                "    scope: all",
                "",
            ]
        ),
    )
    _write_fitness_manifest(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: demo.fail",
                "    name: Demo",
                "    summary: Demo fail",
                "    rationale: Demo rationale",
                "    remediation: Demo remediation",
                "    scope: repo",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                "      - >-",
                '        import json; print(json.dumps({"contract_version": "1.0", "rule_id": "demo.fail", "status": "fail", "severity": "warning", "summary": "nope", "violations": ["v"]}))',
                "",
            ]
        ),
    )

    outcome = run_gate_phase(
        _feature_iteration_inputs(tmp_path),
        archived_in_iteration=False,
        archived_path=None,
        dependencies=_gate_dependencies(
            ChangedPathsResult(paths=(), run_all=True, reason=None)
        ),
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "fitness_all"


def test_run_reviewer_phase_uses_checks_yaml_for_run_all_feature_done(
    tmp_path: Path,
) -> None:
    """Run feature-done reviewer checks against the archived feature state."""
    _write_checks_yaml(
        tmp_path,
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
        ),
    )
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Check docs.\n$responseformat\n", encoding="utf-8")

    archived_feature_path = tmp_path / ARCHIVED_FEATURE_PATH
    archived_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    def _run_agent(
        _project_root: Path,
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
                "decision": "approve",
                "summary": "ok",
                "required_actions": [],
            }
        )

    outcome = run_reviewer_phase(
        _feature_iteration_inputs(tmp_path),
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=archived_feature_path,
        dependencies=ReviewerPhaseDependencies(
            collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
                paths=(),
                run_all=True,
                reason=None,
            ),
            restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            run_agent_fn=_run_agent,
        ),
    )

    assert outcome.result == "passed"
    assert "[reviewer:doc_review] decision=approve" in outcome.reviewer_output


def test_run_reviewer_phase_skips_on_change_reviewer_checks_when_no_match(
    tmp_path: Path,
) -> None:
    """Skip reviewer checks whose on-change globs do not match the diff."""
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                '    prompt_file: "harness/reviewers/prompts/doc_review.md"',
                "    when:",
                "      phase: feature_done",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Check docs.\n$responseformat\n", encoding="utf-8")

    archived_feature_path = tmp_path / ARCHIVED_FEATURE_PATH
    archived_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    outcome = run_reviewer_phase(
        _feature_iteration_inputs(tmp_path),
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=archived_feature_path,
        dependencies=ReviewerPhaseDependencies(
            collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
                paths=("README.md",),
                run_all=False,
                reason=None,
            ),
            restore_archived_feature=lambda *_args, **_kwargs: (True, None),
            run_agent_fn=lambda *_args, **_kwargs: None,
        ),
    )

    assert outcome.result == "passed"
    assert "skip" in outcome.reviewer_output
