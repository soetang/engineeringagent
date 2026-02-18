from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any
from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.loop_runtime.models import FeatureIterationInputs
from engineeringagent.loop_runtime.phases import (
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    run_gate_phase,
    run_reviewer_phase,
    run_verification_phase,
    VerificationPhaseDependencies,
)
from engineeringagent.prompts.retry_feedback import parse_retry_feedback_envelope


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
    assert "invalid harness/checks.yaml" in outcome.gate_output


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

    archived_feature_path = (
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml"
    )
    _write_text(archived_feature_path, "id: FEAT-001\n")

    class _Proc:
        def __init__(self, *, session_id: str, text_payload: str) -> None:
            self.session_id = session_id
            self.text_payload = text_payload
            self.stdout = ""
            self.stderr = ""

    def _start_agent(execution_root: Path, prompt: str, **_kwargs: object) -> _Proc:
        del execution_root, prompt
        return _Proc(
            session_id="sess-123",
            text_payload='{"decision":"request_changes","summary":"needs work","required_actions":["fix it"]}',
        )

    deps = ReviewerPhaseDependencies(
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="fallback_run_all_change_discovery_failed",
        ),
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        start_agent=_start_agent,
    )

    outcome = run_reviewer_phase(
        inputs,
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=archived_feature_path,
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.failed_gate == "reviewer_request_changes"
    assert outcome.reviewer_status == "failed:request_changes"
    assert outcome.hook_feedback

    envelope = parse_retry_feedback_envelope(outcome.hook_feedback)
    assert envelope.kind == "reviewer_feedback"
    assert envelope.phase == "reviewers"
    assert envelope.reviewer_id == "doc_review"
    assert envelope.reviewer_phase == "feature_done"
    assert envelope.decision.summary == "needs work"
    assert envelope.decision.required_actions == ["fix it"]


def test_run_gate_phase_emits_command_failure_retry_feedback_contract(
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
                "    command: echo boom",
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
        run_shell_command=lambda _root, command: SimpleNamespace(
            returncode=2,
            stdout="",
            stderr=f"expected failure for command={command}",
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
    assert outcome.hook_feedback
    assert "expected failure" not in outcome.hook_feedback

    envelope = parse_retry_feedback_envelope(outcome.hook_feedback)
    assert envelope.kind == "command_failure"
    assert envelope.phase == "gates"
    assert envelope.gate == "smoke"
    assert envelope.command == "echo boom"
    assert envelope.precommit is False
    assert envelope.rerun.cwd == "repo_root"


def test_run_verification_phase_emits_command_failure_retry_feedback_contract(
    tmp_path: Path,
) -> None:
    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=False,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    deps = VerificationPhaseDependencies(
        run_shell_command=lambda _root, command: SimpleNamespace(
            returncode=1,
            stdout="",
            stderr=f"verification failure for command={command}",
        ),
    )

    outcome = run_verification_phase(
        inputs,
        verification_commands=["python -c 'raise SystemExit(1)'"],
        dependencies=deps,
    )

    assert outcome.result == "failed"
    assert outcome.verification_failed_command
    assert outcome.hook_feedback
    assert "verification failure" not in outcome.hook_feedback

    envelope = parse_retry_feedback_envelope(outcome.hook_feedback)
    assert envelope.kind == "command_failure"
    assert envelope.phase == "verification"
    assert envelope.gate is None
    assert envelope.command == "python -c 'raise SystemExit(1)'"
    assert envelope.rerun.cwd == "repo_root"


def test_run_gate_phase_emits_fitness_failure_retry_feedback_contract(
    tmp_path: Path,
) -> None:
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
                "    remediation: Fix failing rule.",
                "    scope: repo",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                "      - >-",
                '        import json; print(json.dumps({"contract_version": "1.0", "rule_id": "demo.fail", "status": "fail", "severity": "warning", "summary": "nope", "violations": ["path/to/file.txt:1 broken"]}))',
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
    assert outcome.failed_gate == "fitness_validate"
    assert outcome.hook_feedback

    envelope = parse_retry_feedback_envelope(outcome.hook_feedback)
    assert envelope.kind == "fitness_failure"
    assert envelope.phase == "gates"
    assert envelope.gate == "fitness_validate"
    assert envelope.failed_rules
    assert [rule.rule_id for rule in envelope.failed_rules] == ["demo.fail"]
    assert envelope.failed_rules[0].remediation == "Fix failing rule."
    assert "broken" in envelope.failed_rules[0].violations[0]
