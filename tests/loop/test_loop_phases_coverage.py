from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import cast

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks import ChecksRunResult
from engineeringagent.loop_runtime.models import FeatureIterationInputs
from engineeringagent.loop_runtime.phases import (
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    run_gate_phase,
    run_reviewer_phase,
    run_verification_phase,
)
from engineeringagent.prompts.feedback_envelope import parse_feedback_envelope


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

    assert outcome.result == "failed"
    assert outcome.failed_gate == "checks_config"
    assert outcome.gate_status == "failed:checks_config"


def test_run_gate_phase_reports_load_error_when_checks_document_raises(
    tmp_path: Path,
) -> None:
    _write_text(
        tmp_path / "harness" / "checks.yaml",
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: ''",
                "",
            ]
        )
        + "\n",
    )

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
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

    assert outcome.result == "failed"
    assert outcome.failed_gate == "checks_config"
    assert "invalid harness/checks.yaml" in outcome.gate_output


def test_run_reviewer_phase_forwards_request_changes_feedback_for_run_all(
    tmp_path: Path,
    monkeypatch,
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
        feedback=None,
        verbose_output=False,
    )

    archived_feature_path = (
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml"
    )
    _write_text(archived_feature_path, "id: FEAT-001\n")

    sentinel_feedback = "REVIEWER_FEEDBACK_SENTINEL"
    raw_output = "REVIEWER_RAW_OUTPUT_SHOULD_NOT_BE_FORWARDED"
    recorded_phases: list[object] = []

    def _run_checks(_project_root: Path, **kwargs: object) -> ChecksRunResult:
        recorded_phases.append(kwargs.get("phase"))
        return ChecksRunResult(
            ok=False,
            dry_run=False,
            failed_check_id="doc_review",
            output=raw_output,
            prompt_feedback=sentinel_feedback,
        )

    monkeypatch.setattr("engineeringagent.loop_runtime.phases.run_checks", _run_checks)

    deps = ReviewerPhaseDependencies(
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="fallback_run_all_change_discovery_failed",
        ),
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        run_agent_fn=None,
    )

    outcome = run_reviewer_phase(
        inputs,
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=archived_feature_path,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "doc_review"
    assert outcome.reviewer_status == "failed:doc_review"
    assert outcome.feedback == sentinel_feedback
    assert raw_output not in outcome.feedback
    assert recorded_phases == ["feature_done"]


def test_run_gate_phase_emits_command_failure_feedback_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_text(
        tmp_path / "harness" / "checks.yaml",
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: python -c 'raise SystemExit(1)'",
                "",
            ]
        )
        + "\n",
    )

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
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

    sentinel_feedback = "GATE_FEEDBACK_SENTINEL"
    raw_output = "GATE_RAW_OUTPUT_SHOULD_NOT_BE_FORWARDED"
    monkeypatch.setattr(
        "engineeringagent.loop_runtime.phases.run_checks",
        lambda *_args, **_kwargs: ChecksRunResult(
            ok=False,
            dry_run=False,
            failed_check_id="smoke",
            output=raw_output,
            prompt_feedback=sentinel_feedback,
        ),
    )

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "smoke"
    assert outcome.feedback == sentinel_feedback
    assert raw_output not in outcome.feedback


def test_run_gate_phase_uses_generic_feedback_when_prompt_feedback_missing(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_text(
        tmp_path / "harness" / "checks.yaml",
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: python -c 'raise SystemExit(1)'",
                "",
            ]
        )
        + "\n",
    )

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
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

    raw_output = "RAW_OUTPUT_SHOULD_NOT_BE_FORWARDED"
    monkeypatch.setattr(
        "engineeringagent.loop_runtime.phases.run_checks",
        lambda *_args, **_kwargs: ChecksRunResult(
            ok=False,
            dry_run=False,
            failed_check_id="smoke",
            output=raw_output,
            prompt_feedback="\n  ",
        ),
    )

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.feedback == "checks failed"
    assert raw_output not in outcome.feedback


def test_run_gate_phase_includes_validate_group_for_iteration_end_only(
    tmp_path: Path,
    monkeypatch,
) -> None:
    _write_text(
        tmp_path / "harness" / "checks.yaml",
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "echo ok"',
                "",
            ]
        )
        + "\n",
    )

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
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

    recorded_calls: list[tuple[object, list[str] | None]] = []

    def _run_checks(_project_root: Path, **kwargs: object) -> ChecksRunResult:
        checks = cast(list[str] | None, kwargs.get("checks"))
        recorded_calls.append((kwargs.get("phase"), checks))
        return ChecksRunResult(ok=True, dry_run=False)

    monkeypatch.setattr("engineeringagent.loop_runtime.phases.run_checks", _run_checks)

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml",
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert recorded_calls == [
        ("iteration_end", ["validate", "commands", "fitness"]),
        ("feature_done", ["commands", "fitness"]),
    ]


def test_run_gate_phase_iteration_end_validate_enforces_status_alignment(
    tmp_path: Path,
) -> None:
    command_marker = tmp_path / "command-ran.txt"
    _write_text(
        tmp_path / "harness" / "checks.yaml",
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: >-",
                "      python -c \"from pathlib import Path; Path(",
                f"      r'{command_marker.as_posix()}').write_text('ran', encoding='utf-8')\"",
                "",
            ]
        )
        + "\n",
    )
    _write_text(
        tmp_path / "docs" / "spec" / "features" / "FEAT-001-invalid-status.yaml",
        "\n".join(
            [
                "id: FEAT-001",
                "title: Done but open subtask",
                "type: feature",
                "expected_commit_subject: 'feat: enforce status invariants'",
                "status: done",
                "priority: high",
                "objective: Keep status alignment strict.",
                "acceptance:",
                "  - Validate catches status mismatch.",
                "subtasks:",
                "  - id: ST-001",
                "    title: Open work",
                "    status: backlog",
                "    verification:",
                "      - 'true'",
                "",
            ]
        ),
    )

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path
        / "docs"
        / "spec"
        / "features"
        / "FEAT-001-invalid-status.yaml",
        run_all=True,
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

    assert outcome.result == "failed"
    assert outcome.failed_gate == "validate"
    assert outcome.gate_status == "failed:validate"
    assert "feature status done requires all subtasks done" in outcome.gate_output
    assert not command_marker.exists()


def test_run_verification_phase_emits_command_failure_feedback_contract(
    tmp_path: Path,
    monkeypatch,
) -> None:
    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )

    monkeypatch.setattr(
        "engineeringagent.loop_runtime.phases.run_shell_command",
        lambda _root, command: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=f"verification failure for command={command}",
        ),
    )

    outcome = run_verification_phase(
        inputs,
        verification_commands=["python -c 'raise SystemExit(1)'"],
    )

    assert outcome.result == "failed"
    assert outcome.verification_failed_command
    assert outcome.feedback
    assert "verification failure" not in outcome.feedback

    envelope = parse_feedback_envelope(outcome.feedback)
    assert envelope.kind == "command_failure"
    assert envelope.phase == "verification"
    assert envelope.gate is None
    assert envelope.command == "python -c 'raise SystemExit(1)'"
    assert envelope.rerun.cwd == "repo_root"


def test_run_verification_phase_reports_parse_failures_with_stable_output(
    tmp_path: Path,
) -> None:
    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    command = 'python -c "print(1)'

    outcome = run_verification_phase(
        inputs,
        verification_commands=[command],
    )

    assert outcome.result == "failed"
    assert outcome.verification_status == f"failed:{command}"
    assert outcome.verification_failed_command == command
    assert f"[verification] command={command}" in outcome.verification_output
    assert "[verification] returncode=2" in outcome.verification_output
    assert "command parse error:" in outcome.verification_output
    assert "Remediation: provide a plain argv-style command" in outcome.verification_output


def test_run_verification_phase_reports_missing_executable_with_stable_output(
    tmp_path: Path,
) -> None:
    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=False,
        attempt=1,
        feedback=None,
        verbose_output=False,
    )
    command = "missing-executable-for-feat-159-verification"

    outcome = run_verification_phase(
        inputs,
        verification_commands=[command],
    )

    assert outcome.result == "failed"
    assert outcome.verification_status == f"failed:{command}"
    assert outcome.verification_failed_command == command
    assert f"[verification] command={command}" in outcome.verification_output
    assert "[verification] returncode=127" in outcome.verification_output
    assert f"command executable not found: {command}" in outcome.verification_output
    assert "Remediation: install the executable" in outcome.verification_output


def test_run_gate_phase_emits_fitness_failure_feedback_contract(
    tmp_path: Path,
) -> None:
    remediation = "FITNESS_REMEDIATION_SENTINEL"
    raw_output_token = "FITNESS_RAW_OUTPUT_SENTINEL"
    _write_text(
        tmp_path / "harness" / "checks.yaml",
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_validate:",
                "    type: fitness",
                "    scope: all",
                "",
            ]
        )
        + "\n",
    )
    _write_text(
        tmp_path / "harness" / "fitness-functions" / "rules.yaml",
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
                "  - rule_id: demo.fail",
                "    name: Demo",
                "    summary: Demo fail",
                "    rationale: Demo rationale",
                f"    remediation: {remediation}",
                "    scope: repo",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                "      - >-",
                f'        import json; print(json.dumps({{"contract_version": "1.0", "rule_id": "demo.fail", "status": "fail", "severity": "warning", "summary": "{raw_output_token}", "violations": ["path/to/file.txt:1 broken"]}}))',
                "",
            ]
        )
        + "\n",
    )

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
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

    assert outcome.result == "failed"
    assert outcome.failed_gate == "fitness_validate"
    feedback = outcome.feedback
    assert feedback is not None
    assert "fitness_validate" in feedback
    assert "demo.fail" in feedback
    assert remediation in feedback
    assert raw_output_token not in feedback
