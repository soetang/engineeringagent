from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.commands.runtime import (
    PlannedCheck as CommandPlannedCheck,
    RunPlannedCommandChecksRequest,
    iter_planned_command_check_commands,
    plan_command_checks,
    run_planned_command_checks,
)
from engineeringagent.checks.fitness.runtime import (
    PlannedCheck as FitnessPlannedCheck,
    RunPlannedFitnessChecksRequest,
    plan_fitness_checks,
    run_planned_fitness_checks,
)
from engineeringagent.checks.reviewers.runtime import (
    PlannedCheck as ReviewerPlannedCheck,
    RunPlannedReviewerChecksRequest,
    iter_planned_reviewer_checks,
    plan_reviewer_checks,
    run_planned_reviewer_checks,
)
from engineeringagent.loop_runtime.models import FeatureIterationInputs
from engineeringagent.loop_runtime.phases import (
    GatePhaseDependencies,
    ReviewerPhaseDependencies,
    run_gate_phase,
    run_reviewer_phase,
)
from engineeringagent.specs import HarnessCheckPhase, HarnessChecksDocument, load_yaml


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def _load_checks_document(checks_path: Path) -> HarnessChecksDocument:
    payload = load_yaml(checks_path)
    return HarnessChecksDocument.model_validate(payload)


# Backwards-compatible alias to reduce test churn as the checks migration
# deletes legacy runtimes.
load_checks_document = _load_checks_document


def _write_fitness_manifest(tmp_path: Path, content: str) -> Path:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(content, encoding="utf-8")
    return manifest_path


def test_run_gate_phase_uses_checks_yaml_for_run_all_iteration_end(
    tmp_path: Path,
) -> None:
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
        run_shell_command=lambda _root, command: __import__("subprocess").run(
            command,
            shell=True,
            cwd=_root,
            capture_output=True,
            text=True,
        ),
    )

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.gate_status == "passed"
    assert "[check:smoke]" in outcome.gate_output


def test_run_gate_phase_skips_on_change_command_checks_when_no_match(
    tmp_path: Path,
) -> None:
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
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
        run_shell_command=lambda _root, command: SimpleNamespace(
            returncode=1,
            stdout="unexpected",
            stderr="",
        ),
    )

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert outcome.gate_output == ""


def test_run_gate_phase_runs_feature_done_checks_only_when_archived(
    tmp_path: Path,
) -> None:
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

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    calls: list[str] = []

    def _run(_root: Path, command: str) -> Any:
        calls.append(command)
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    deps = GatePhaseDependencies(
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
        run_shell_command=_run,
    )

    run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )
    assert calls == ["echo iter"]

    calls.clear()
    run_gate_phase(
        inputs,
        archived_in_iteration=True,
        archived_path=tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml",
        dependencies=deps,
    )
    assert calls == ["echo iter", "echo done"]


def test_run_gate_phase_runs_fitness_checks_scope_all(
    tmp_path: Path,
) -> None:
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
            returncode=1,
            stdout="unexpected",
            stderr="",
        ),
    )

    outcome = run_gate_phase(
        inputs,
        archived_in_iteration=False,
        archived_path=None,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert "[check:fitness_all]" in outcome.gate_output
    assert "[fitness:demo.pass] status=pass" in outcome.gate_output


def test_run_gate_phase_fails_when_fitness_check_fails(
    tmp_path: Path,
) -> None:
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
    assert outcome.failed_gate == "fitness_all"


def test_run_reviewer_phase_uses_checks_yaml_for_run_all_feature_done(
    tmp_path: Path,
) -> None:
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

    archived_feature_path = (
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml"
    )
    archived_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    reviewer_state: dict[str, Any] = {"version": "1", "features": {}}

    def _start_agent(*_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(
            returncode=0,
            stdout='{"decision":"approve","summary":"ok","required_actions":[]}',
            stderr="",
        )

    deps = ReviewerPhaseDependencies(
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
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

    assert outcome.result == "passed"
    assert "[reviewer:doc_review] decision=approve" in outcome.reviewer_output


def test_run_reviewer_phase_skips_on_change_reviewer_checks_when_no_match(
    tmp_path: Path,
) -> None:
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

    archived_feature_path = (
        tmp_path / "docs" / "spec" / "features_done" / "FEAT-001.yaml"
    )
    archived_feature_path.parent.mkdir(parents=True, exist_ok=True)
    archived_feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    inputs = FeatureIterationInputs(
        project_root=tmp_path,
        feature_path=tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml",
        run_all=True,
        attempt=1,
        hook_feedback=None,
        verbose_output=False,
    )

    deps = ReviewerPhaseDependencies(
        collect_changed_paths=lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
        restore_archived_feature=lambda *_args, **_kwargs: (True, None),
        start_agent=lambda *_args, **_kwargs: None,
    )

    outcome = run_reviewer_phase(
        inputs,
        {"id": "FEAT-001"},
        archived_in_iteration=True,
        archived_path=archived_feature_path,
        dependencies=deps,
    )

    assert outcome.result == "passed"
    assert "skip" in outcome.reviewer_output


def test_plan_command_checks_manual_phase_skips(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "    when:",
                "      phase: manual",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
    )

    assert [p.model_dump() for p in planned] == [
        {"check_id": "smoke", "decision": "skip", "reason": "manual"}
    ]


def test_plan_command_checks_runs_when_run_all_change_discovery_fallback(
    tmp_path: Path,
) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  ruff:",
                "    type: command",
                "    command: echo ruff",
                "    when:",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)
    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="change_discovery_failed",
        ),
    )
    assert [p.model_dump() for p in planned] == [
        {
            "check_id": "ruff",
            "decision": "run",
            "reason": "change_discovery_failed",
        }
    ]


def test_plan_command_checks_runs_when_on_change_matches(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  ruff:",
                "    type: command",
                "    command: echo ruff",
                "    when:",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/cli.py",),
            run_all=False,
            reason=None,
        ),
    )

    assert planned[0].decision == "run"
    assert planned[0].reason == "matched_on_change"


def test_plan_command_checks_uses_defaults_when_phase(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "defaults:",
                "  when:",
                "    phase: feature_done",
                "checks:",
                "  done_only:",
                "    type: command",
                "    command: echo done",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
    )

    assert [entry.check_id for entry in planned] == ["done_only"]


def test_plan_fitness_checks_manual_phase_skips(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_all:",
                "    type: fitness",
                "    scope: all",
                "    when:",
                "      phase: manual",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_fitness_checks(
        doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
    )

    assert [p.model_dump() for p in planned] == [
        {"check_id": "fitness_all", "decision": "skip", "reason": "manual"}
    ]


def test_plan_fitness_checks_skips_when_phase_mismatch(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_done:",
                "    type: fitness",
                "    scope: all",
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_fitness_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
    )
    assert planned == []


def test_plan_fitness_checks_runs_when_run_all_change_discovery_fallback(
    tmp_path: Path,
) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_on_change:",
                "    type: fitness",
                "    scope: all",
                "    when:",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_fitness_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="change_discovery_failed",
        ),
    )
    assert planned[0].decision == "run"
    assert planned[0].reason == "change_discovery_failed"


def test_plan_fitness_checks_runs_when_on_change_matches(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_on_change:",
                "    type: fitness",
                "    scope: all",
                "    when:",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_fitness_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/cli.py",),
            run_all=False,
            reason=None,
        ),
    )
    assert planned[0].decision == "run"
    assert planned[0].reason == "matched_on_change"


def test_plan_reviewer_checks_runs_when_on_change_matches(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
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
                "      on_change: ['docs/**/*.md']",
                "",
            ]
        ),
    )
    (tmp_path / "harness" / "reviewers" / "prompts").mkdir(parents=True, exist_ok=True)
    (tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md").write_text(
        "$responseformat\n",
        encoding="utf-8",
    )
    doc = load_checks_document(checks_path)

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(
            paths=("docs/README.md",),
            run_all=False,
            reason=None,
        ),
    )

    assert planned[0].decision == "run"
    assert planned[0].reason == "matched_on_change"


def test_plan_reviewer_checks_manual_phase_skips(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                '    prompt_file: "harness/reviewers/prompts/doc_review.md"',
                "    when:",
                "      phase: manual",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
    )

    assert [p.model_dump() for p in planned] == [
        {"check_id": "doc_review", "decision": "skip", "reason": "manual"}
    ]


def test_plan_reviewer_checks_runs_when_run_all_change_discovery_fallback(
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
                '    prompt_file: "harness/reviewers/prompts/doc_review.md"',
                "    when:",
                "      phase: feature_done",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="change_discovery_failed",
        ),
    )

    assert planned[0].decision == "run"
    assert planned[0].reason == "change_discovery_failed"


def test_plan_reviewer_checks_skips_non_reviewer_and_phase_mismatch(
    tmp_path: Path,
) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "  doc_review:",
                "    type: reviewer",
                '    prompt_file: "harness/reviewers/prompts/doc_review.md"',
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = plan_reviewer_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
    )

    assert planned == []


def test_iter_planned_reviewer_checks_skips_non_reviewer_ids(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = [ReviewerPlannedCheck(check_id="smoke", decision="run", reason="always")]
    yielded = list(
        iter_planned_reviewer_checks(
            doc,
            planned,
        )
    )
    assert yielded == []


def test_iter_planned_command_check_commands_skips_non_run(tmp_path: Path) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = [CommandPlannedCheck(check_id="smoke", decision="skip", reason="manual")]
    yielded = list(
        iter_planned_command_check_commands(
            doc,
            planned,
        )
    )
    assert yielded == []


def test_iter_planned_command_check_commands_skips_non_command_defs(
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
                '    prompt_file: "harness/reviewers/prompts/doc_review.md"',
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    planned = [
        CommandPlannedCheck(check_id="doc_review", decision="run", reason="always")
    ]
    yielded = list(iter_planned_command_check_commands(doc, planned))
    assert yielded == []


def test_run_planned_command_checks_fails_and_emits_verbose_output(
    tmp_path: Path,
    capsys: Any,
) -> None:
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "",
            ]
        ),
    )
    doc = load_checks_document(checks_path)

    def _run(_root: Path, _command: str) -> Any:
        return type(
            "Proc",
            (),
            {"returncode": 7, "stdout": "stdout\n", "stderr": "stderr\n"},
        )()

    request = RunPlannedCommandChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
        verbose_output=True,
    )
    ok, failed, output = run_planned_command_checks(request, run_shell_command=_run)

    assert ok is False
    assert failed == "smoke"
    assert "[check:smoke] returncode=7" in output
    captured = capsys.readouterr().out
    assert "stdout" in captured
    assert "stderr" in captured


def test_run_planned_fitness_checks_fails_on_missing_rule_ids(tmp_path: Path) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_subset:",
                "    type: fitness",
                "    rule_ids: ['demo.present', 'demo.missing']",
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
                "  - rule_id: demo.present",
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
                '        import json; print(json.dumps({"contract_version": "1.0", "rule_id": "demo.present", "status": "pass", "severity": "warning", "summary": "ok", "violations": []}))',
                "",
            ]
        ),
    )

    doc = load_checks_document(tmp_path / "harness" / "checks.yaml")
    request = RunPlannedFitnessChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
    )
    ok, failed, output = run_planned_fitness_checks(request)

    assert ok is False
    assert failed == "fitness_subset"
    assert "missing_rule_ids" in output


def test_run_planned_fitness_checks_runs_only_requested_rule_ids(
    tmp_path: Path,
) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_subset:",
                "    type: fitness",
                "    rule_ids: ['demo.one']",
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
                "  - rule_id: demo.one",
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
                '        import json; print(json.dumps({"contract_version": "1.0", "rule_id": "demo.one", "status": "pass", "severity": "warning", "summary": "ok", "violations": []}))',
                "  - rule_id: demo.two",
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
                '        import json; print(json.dumps({"contract_version": "1.0", "rule_id": "demo.two", "status": "pass", "severity": "warning", "summary": "ok", "violations": []}))',
                "",
            ]
        ),
    )

    doc = load_checks_document(tmp_path / "harness" / "checks.yaml")
    request = RunPlannedFitnessChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
    )
    ok, failed, output = run_planned_fitness_checks(request)

    assert ok is True
    assert failed is None
    assert "[fitness:demo.one]" in output
    assert "[fitness:demo.two]" not in output


def test_run_planned_fitness_checks_skips_when_decision_is_skip(
    tmp_path: Path,
) -> None:
    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_on_change:",
                "    type: fitness",
                "    scope: all",
                "    when:",
                "      on_change: ['src/**/*.py']",
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
    doc = load_checks_document(tmp_path / "harness" / "checks.yaml")

    request = RunPlannedFitnessChecksRequest(
        project_root=tmp_path,
        doc=doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=("README.md",),
            run_all=False,
            reason=None,
        ),
    )
    ok, failed, output = run_planned_fitness_checks(request)

    assert ok is True
    assert failed is None
    assert output == ""
