from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys

import pytest

from engineeringagent import checks
from engineeringagent.checks import (
    ChangedPathsResult,
    ChecksRunResult,
    FALLBACK_CHANGE_DISCOVERY_REASON,
    HarnessCheckPhase,
    collect_changed_paths,
    custom_rule_manifest_schema_from_model,
    emit_fitness_result,
    iter_feature_files,
    list_check_groups,
    load_markdown_frontmatter,
    load_harness_checks_document,
    normalize_groups,
    resolve_feature_plan_path,
    render_fitness_catalog,
    reviewer_decision_schema_from_model,
    reviewers_group_selected,
    run_checks,
    validate_repository,
)
from engineeringagent.checks.results import ChecksRunResult as ChecksRunResultModel
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


def test_checks_supported_exports_are_importable() -> None:
    """Checks package should expose the supported FEAT-178 public surface."""
    assert callable(run_checks)
    assert callable(emit_fitness_result)
    assert callable(iter_feature_files)
    assert callable(list_check_groups)
    assert callable(load_markdown_frontmatter)
    assert callable(load_harness_checks_document)
    assert callable(normalize_groups)
    assert callable(resolve_feature_plan_path)
    assert callable(render_fitness_catalog)
    assert callable(custom_rule_manifest_schema_from_model)
    assert callable(reviewer_decision_schema_from_model)
    assert callable(validate_repository)
    assert callable(collect_changed_paths)
    assert ChecksRunResult is not None
    assert ChangedPathsResult is not None
    assert FALLBACK_CHANGE_DISCOVERY_REASON == "fallback_run_all_change_discovery_failed"
    assert HarnessCheckPhase.ITERATION_END.value == "iteration_end"
    assert set(checks.__all__) == {
        "ChangedPathsResult",
        "ChecksRunResult",
        "FALLBACK_CHANGE_DISCOVERY_REASON",
        "HarnessCheckPhase",
        "collect_changed_paths",
        "custom_rule_manifest_schema_from_model",
        "emit_fitness_result",
        "iter_feature_files",
        "list_check_groups",
        "load_markdown_frontmatter",
        "load_harness_checks_document",
        "normalize_groups",
        "resolve_feature_plan_path",
        "render_fitness_catalog",
        "reviewer_decision_schema_from_model",
        "reviewers_group_selected",
        "run_checks",
        "validate_repository",
    }


def test_checks_public_helpers_remain_usable_from_package_facade(
    tmp_path: Path,
) -> None:
    """Checks facade helpers should keep their user-visible behavior."""
    doc, error = load_harness_checks_document(
        tmp_path,
        error_prefix="checks config error",
        missing_context="missing harness/checks.yaml",
    )
    assert doc is None
    assert error is not None
    assert error.startswith("checks config error: missing harness/checks.yaml")
    assert "engineeringagent init" in error


def test_schema_helpers_remain_available_from_package_facade() -> None:
    """Checks schema helpers should stay usable from the package facade."""
    assert custom_rule_manifest_schema_from_model()["title"]
    assert reviewer_decision_schema_from_model()["title"]


def test_feature_plan_resolver_remains_available_from_package_facade(
    tmp_path: Path,
) -> None:
    """Checks facade should expose the bundled feature plan resolver for harness code."""
    spec_path = tmp_path / "docs/spec/features/FEAT-181/spec.yaml"
    spec_path.parent.mkdir(parents=True)

    resolved = resolve_feature_plan_path(
        spec_path,
        {
            "artifacts": {
                "plan": "planning/plan.md",
            }
        },
    )

    assert resolved == spec_path.parent / "planning/plan.md"


def test_bundled_spec_helpers_remain_available_from_package_facade(
    tmp_path: Path,
) -> None:
    """Checks facade should expose bundled spec helpers for harness scripts."""
    features_dir = tmp_path / "docs/spec/features"
    bundled_root = features_dir / "FEAT-181-bundled"
    bundled_root.mkdir(parents=True)
    spec_path = bundled_root / "spec.yaml"
    spec_path.write_text("id: FEAT-181\n", encoding="utf-8")
    plan_path = bundled_root / "plan.md"
    plan_path.write_text(
        "---\nstatus: backlog\nphases: []\n---\n# Plan\n",
        encoding="utf-8",
    )

    assert tuple(iter_feature_files(features_dir)) == (spec_path,)
    assert load_markdown_frontmatter(plan_path) == {
        "status": "backlog",
        "phases": [],
    }


def test_checks_run_result_remains_importable_after_specs_import(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Checks run-result export should preserve the moved public contract."""
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_path
        if not existing_pythonpath
        else os.pathsep.join((src_path, existing_pythonpath))
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import engineeringagent.specs; "
                "from engineeringagent.checks import ChecksRunResult; "
                "from engineeringagent.checks.results import ChecksRunResult as ResultsChecksRunResult; "
                "assert ChecksRunResult is ResultsChecksRunResult; "
                "result = ChecksRunResult.model_validate({"
                "'ok': True, "
                "'decisions': ({'check_id': 'smoke', 'check_type': 'command', 'phase': 'iteration_end', 'decision': 'run', 'reason': 'selected'},), "
                "'executions': ({'check_id': 'smoke', 'check_type': 'command', 'ok': True, 'output': 'ok\\n', 'payload': {'stdout': 'ok\\n'}},), "
                "'command_invocations': ({'check_id': 'smoke', 'command': 'echo ok', 'returncode': 0, 'started_epoch_sec': 1, 'ended_epoch_sec': 2, 'started_monotonic_ns': 3, 'finished_monotonic_ns': 4, 'duration_ms': 1.5},)"
                "}); "
                "assert result.executions[0].check_id == 'smoke'; "
                "assert result.command_invocations[0].command == 'echo ok'"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_checks_supported_contracts_remain_usable_after_specs_import(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Specs imports should not break checks-owned public contracts."""
    env = os.environ.copy()
    src_path = str(repo_root / "src")
    existing_pythonpath = env.get("PYTHONPATH")
    env["PYTHONPATH"] = (
        src_path
        if not existing_pythonpath
        else os.pathsep.join((src_path, existing_pythonpath))
    )

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import engineeringagent.specs; "
                "from engineeringagent.checks import HarnessCheckPhase, normalize_groups; "
                "assert HarnessCheckPhase.ITERATION_END.value == 'iteration_end'; "
                "assert normalize_groups(['fitness', 'commands']) == ('commands', 'fitness')"
            ),
        ],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stderr


def test_checks_group_helpers_use_deterministic_contract() -> None:
    """Checks group helpers should preserve stable normalization behavior."""
    assert list_check_groups() == ("validate", "commands", "fitness", "reviewers")
    assert normalize_groups(["fitness", "commands", "fitness"]) == (
        "commands",
        "fitness",
    )


def test_checks_group_helpers_cover_public_behavior() -> None:
    """Checks group helpers should remain available from the package facade."""
    assert reviewers_group_selected(["reviewers"]) is True
    assert reviewers_group_selected(["validate"]) is False
    assert checks.reviewers_group_selected(["reviewers"]) is True


def test_checks_run_result_model_validation_preserves_runtime_data() -> None:
    """Run-result validation should preserve runtime data on nested records."""
    result = ChecksRunResultModel.model_validate(
        {
            "ok": True,
            "decisions": (
                {
                    "check_id": "smoke",
                    "check_type": "command",
                    "phase": "iteration_end",
                    "decision": "run",
                    "reason": "selected",
                },
            ),
            "executions": (
                {
                    "check_id": "smoke",
                    "check_type": "command",
                    "ok": True,
                    "output": "ok\n",
                    "payload": {"stdout": "ok\n"},
                },
            ),
            "command_invocations": (
                {
                    "check_id": "smoke",
                    "command": "echo ok",
                    "returncode": 0,
                    "started_epoch_sec": 1,
                    "ended_epoch_sec": 2,
                    "started_monotonic_ns": 3,
                    "finished_monotonic_ns": 4,
                    "duration_ms": 1.5,
                },
            ),
        }
    )

    assert result.decisions[0]["check_id"] == "smoke"
    assert result.executions[0].check_id == "smoke"
    assert result.command_invocations[0].command == "echo ok"


@pytest.mark.parametrize(
    "legacy_name",
    [
        "load_reviewer_config",
        "parse_reviewer_decision",
        "plan_reviewers",
        "run_planned_command_checks",
        "run_planned_fitness_checks",
        "run_planned_reviewer_checks",
    ],
)
def test_checks_does_not_export_removed_legacy_runtime_helpers(legacy_name: str) -> None:
    """Removed legacy helpers should stay absent from the checks facade."""
    assert legacy_name not in checks.__all__
    assert not hasattr(checks, legacy_name)


def test_checks_does_not_export_emit_result_envelope_alias() -> None:
    """Legacy emit-result alias should remain absent from the checks facade."""
    assert "emit_result_envelope" not in checks.__all__
    assert not hasattr(checks, "emit_result_envelope")


def test_checks_emit_fitness_result_is_deterministic_and_validates(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Fitness result emission should remain deterministic and schema-valid."""
    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id="architecture.dep-direction",
            status=RuleStatus.PASS,
            severity=RuleSeverity.ERROR,
            summary="Boundary contract is satisfied.",
            violations=[],
        )
    )

    stdout = capsys.readouterr().out
    expected = (
        '{"contract_version":"1.0",'
        '"rule_id":"architecture.dep-direction",'
        '"status":"pass",'
        '"severity":"error",'
        '"summary":"Boundary contract is satisfied.",'
        '"violations":[]}\n'
    )
    assert stdout == expected
