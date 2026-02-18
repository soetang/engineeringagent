from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness-functions"
        / "check_backend_literal_locality_budget.py"
    )


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def test_backend_literal_locality_budget_rule_registered() -> None:
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)

    rules = manifest.get("rules")
    assert isinstance(rules, list)

    matching: list[dict[str, object]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("rule_id") == "architecture.backend-literal-locality-budget":
            matching.append(rule)

    assert len(matching) == 1

    command = matching[0].get("command")
    assert isinstance(command, list)
    assert (
        "harness/fitness-functions/check_backend_literal_locality_budget.py" in command
    )

    assert Path(
        "harness/fitness-functions/check_backend_literal_locality_budget.py"
    ).exists()


def test_backend_literal_locality_budget_rule_passes_clean_repo() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "harness/fitness-functions/check_backend_literal_locality_budget.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0

    payload = json.loads(proc.stdout)
    assert payload["rule_id"] == "architecture.backend-literal-locality-budget"
    assert payload["status"] == "pass"
    summary = payload.get("summary")
    assert isinstance(summary, str)
    assert "observed=" in summary
    assert "baseline=" in summary

    details = payload.get("details")
    assert isinstance(details, dict)
    baseline_count = details["baseline_violation_count"]
    observed_count = details["observed_violation_count"]
    assert isinstance(baseline_count, int)
    assert isinstance(observed_count, int)
    assert observed_count <= baseline_count
    assert f"observed={observed_count}" in summary
    assert f"baseline={baseline_count}" in summary
    assert details["baseline_refresh_recommended"] is True
    assert details["baseline_refresh_target_violation_count"] == observed_count
    assert details["baseline_refresh_delta"] == (observed_count - baseline_count)
    assert details["tokens"] == sorted(details["tokens"])


def test_backend_literal_locality_budget_rule_reports_deterministic_violations(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/loop_runtime/violations.py",
        "\n".join(
            [
                'TITLE = "OpenCode backend"',
                'SCOPED_DIR = ".opencode"',
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.backend-literal-locality-budget"
    assert payload["status"] == "fail"
    summary = payload.get("summary")
    assert isinstance(summary, str)

    violations = payload.get("violations")
    assert isinstance(violations, list)
    assert violations == sorted(violations)
    assert len(violations) == 2
    assert any(
        "src/engineeringagent/loop_runtime/violations.py:1:" in violation
        and "backend literal token 'OpenCode'" in violation
        for violation in violations
    ), violations
    assert any(
        "src/engineeringagent/loop_runtime/violations.py:2:" in violation
        and "backend literal token '.opencode'" in violation
        for violation in violations
    ), violations

    details = payload.get("details")
    assert isinstance(details, dict)
    baseline_count = details["baseline_violation_count"]
    observed_count = details["observed_violation_count"]
    assert isinstance(baseline_count, int)
    assert isinstance(observed_count, int)
    assert observed_count == 2
    assert observed_count > baseline_count
    assert f"observed={observed_count}" in summary
    assert f"baseline={baseline_count}" in summary
    assert details["baseline_refresh_recommended"] is False
    assert details["baseline_refresh_target_violation_count"] == baseline_count
    assert details["baseline_refresh_delta"] == 0
    assert isinstance(details["tokens"], list)
    assert details["tokens"] == sorted(details["tokens"])


def test_backend_literal_locality_budget_rule_detects_identifier_tokens(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/runtime_backend_coupling.py",
        "\n".join(
            [
                "from engineeringagent.agents.backends.opencode.client import DEFAULT_OPENCODE_AGENT",
                "BACKEND_NAME = 'opencode'",
                "",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    violations = payload.get("violations")
    assert isinstance(violations, list)
    assert len(violations) == 2
    assert any(
        "src/engineeringagent/runtime_backend_coupling.py:1:" in violation
        and "DEFAULT_OPENCODE_AGENT" in violation
        for violation in violations
    ), violations
    assert any(
        "src/engineeringagent/runtime_backend_coupling.py:2:" in violation
        and "backend literal token 'opencode'" in violation
        for violation in violations
    ), violations


def test_backend_literal_locality_budget_rule_recommends_refresh_when_observed_drops(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/runtime_clean.py",
        "RUNTIME_MODE = 'core'\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    summary = payload.get("summary")
    assert isinstance(summary, str)
    assert "observed=" in summary
    assert "baseline=" in summary

    details = payload.get("details")
    assert isinstance(details, dict)
    baseline_count = details["baseline_violation_count"]
    observed_count = details["observed_violation_count"]
    assert isinstance(baseline_count, int)
    assert isinstance(observed_count, int)
    assert observed_count == 0
    assert observed_count < baseline_count
    assert f"observed={observed_count}" in summary
    assert f"baseline={baseline_count}" in summary
    assert details["baseline_refresh_recommended"] is True
    assert details["baseline_refresh_target_violation_count"] == observed_count
    assert details["baseline_refresh_delta"] == (observed_count - baseline_count)
