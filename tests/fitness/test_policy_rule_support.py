from __future__ import annotations

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.checks.fitness.local_support_loader import (
    load_local_support_module,
)


def _load_support_module(repo_root: Path):
    support_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "policy_rule_support.py"
    )
    spec = importlib.util.spec_from_file_location(
        "engineeringagent_tests.policy_rule_support",
        support_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_checker_module(repo_root: Path, script_name: str):
    checker_path = (
        repo_root / "harness" / "fitness_functions" / "rules" / script_name
    )
    spec = importlib.util.spec_from_file_location(
        f"engineeringagent_tests.{script_name.removesuffix('.py')}",
        checker_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_modules_can_load_policy_support_without_sys_path_hacks(
    repo_root: Path,
) -> None:
    dependency_checker = _load_checker_module(
        repo_root,
        "check_dependency_directionality.py",
    )
    statement_budget_checker = _load_checker_module(
        repo_root,
        "check_module_statement_budget.py",
    )
    hermetic_isolation_checker = _load_checker_module(
        repo_root,
        "check_hermetic_fitness_test_isolation.py",
    )

    assert dependency_checker.RULE_ID == "architecture.dep-directionality"
    assert statement_budget_checker.RULE_ID == "architecture.module-statement-budget"
    assert (
        hermetic_isolation_checker.RULE_ID
        == "architecture.hermetic-fitness-test-isolation"
    )


def test_shared_local_support_loader_loads_sibling_module_by_caller_path(
    repo_root: Path,
) -> None:
    checker_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_hermetic_fitness_test_isolation.py"
    )

    support = load_local_support_module(
        "hermetic_fitness_test_isolation_support",
        caller_file=checker_path,
    )

    assert support.TaintState.__name__ == "TaintState"
    assert callable(support.scan_statement)


def test_load_yaml_policy_requires_mapping_payload(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    support = _load_support_module(repo_root)
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("- not-a-mapping\n", encoding="utf-8")

    with pytest.raises(ValueError, match="policy config must be a mapping"):
        support.load_yaml_policy(policy_path)


def test_load_yaml_policy_reports_invalid_yaml(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    support = _load_support_module(repo_root)
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("rules: [\n", encoding="utf-8")

    with pytest.raises(ValueError, match="policy config is not valid YAML"):
        support.load_yaml_policy(policy_path)


def test_run_policy_rule_emits_fail_contract_for_violations(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    support = _load_support_module(repo_root)
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text("rules: []\n", encoding="utf-8")
    monkeypatch.setattr(
        support,
        "parse_policy_args",
        lambda _default_policy: SimpleNamespace(config_file=str(policy_path)),
    )

    exit_code = support.run_policy_rule(
        rule_id="test.policy-rule",
        default_policy=tmp_path / "default.yaml",
        pass_summary="unused",
        fail_summary=lambda count: f"violations={count}",
        error_summary_prefix="policy rule failed",
        evaluate=lambda _project_root, _config_file: ["first", "second"],
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["rule_id"] == "test.policy-rule"
    assert payload["status"] == "fail"
    assert payload["summary"] == "violations=2"
    assert payload["violations"] == ["first", "second"]


def test_run_policy_rule_emits_error_contract_for_missing_policy_file(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    support = _load_support_module(repo_root)
    missing_policy = tmp_path / "missing-policy.yaml"
    monkeypatch.setattr(
        support,
        "parse_policy_args",
        lambda _default_policy: SimpleNamespace(config_file=str(missing_policy)),
    )

    exit_code = support.run_policy_rule(
        rule_id="test.policy-rule",
        default_policy=tmp_path / "default.yaml",
        pass_summary="unused",
        fail_summary=lambda count: f"violations={count}",
        error_summary_prefix="policy rule failed",
        evaluate=lambda _project_root, _config_file: [],
    )
    payload = json.loads(capsys.readouterr().out)

    assert exit_code == 0
    assert payload["rule_id"] == "test.policy-rule"
    assert payload["status"] == "error"
    assert payload["violations"] == []
    assert payload["summary"] == f"policy rule failed: policy config not found: {missing_policy}"
