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
    extra_argv: tuple[str, ...] = (),
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path), *extra_argv],
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

    matching = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.backend-literal-locality-budget"
    ]

    assert len(matching) == 1

    command = matching[0].get("command")
    assert isinstance(command, list)
    assert (
        "harness/fitness-functions/check_backend_literal_locality_budget.py" in command
    )

    assert (
        matching[0].get("config_file")
        == "policies/backend_literal_locality_budget.yaml"
    )

    assert Path(
        "harness/fitness-functions/check_backend_literal_locality_budget.py"
    ).exists()


def test_backend_literal_locality_budget_policy_defines_backend_tokens() -> None:
    policy_path = Path(
        "harness/fitness-functions/policies/backend_literal_locality_budget.yaml"
    )
    policy = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    assert isinstance(policy, dict)

    assert policy.get("rule_id") == "architecture.backend-literal-locality-budget"

    allowed_roots = policy.get("allowed_literal_roots")
    assert isinstance(allowed_roots, list)
    assert allowed_roots == [
        "src/engineeringagent/agents",
        "src/engineeringagent/checks",
    ]

    backends = policy.get("backends")
    assert isinstance(backends, dict)
    assert set(backends) >= {"opencode", "codex"}

    for backend_id in ("opencode", "codex"):
        backend = backends.get(backend_id)
        assert isinstance(backend, dict)
        tokens = backend.get("tokens")
        assert isinstance(tokens, list)
        assert tokens
        assert tokens == sorted(set(tokens))

    assert "OpenCode" in backends["opencode"]["tokens"]
    assert "opencode" in backends["opencode"]["tokens"]
    assert "DEFAULT_CODEX_AGENT" in backends["codex"]["tokens"]
    assert "DEFAULT_CODEX_AGENT_MODEL" in backends["codex"]["tokens"]


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


def test_backend_literal_locality_budget_rule_detects_codex_tokens(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/runtime_backend_coupling.py",
        "BACKEND_MODEL = DEFAULT_CODEX_AGENT_MODEL\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    violations = payload.get("violations")
    assert isinstance(violations, list)
    assert len(violations) == 1
    assert (
        "src/engineeringagent/runtime_backend_coupling.py:1:" in violations[0]
        and "backend literal token 'DEFAULT_CODEX_AGENT_MODEL'" in violations[0]
    )


def test_backend_literal_locality_budget_policy_errors_are_deterministic(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/runtime_backend_coupling.py",
        "BACKEND_NAME = 'core'\n",
    )
    policy_path = tmp_path / "policy.yaml"
    policy_path.write_text(
        "rule_id: architecture.other-rule\n"
        "allowed_literal_roots:\n"
        "  - src/engineeringagent/agents\n"
        "backends:\n"
        "  opencode:\n"
        "    tokens:\n"
        "      - opencode\n",
        encoding="utf-8",
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        extra_argv=("--config-file", str(policy_path)),
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.backend-literal-locality-budget"
    assert payload["status"] == "error"
    summary = payload.get("summary")
    assert isinstance(summary, str)
    assert summary.startswith("Invalid backend literal locality policy configuration:")
    assert "rule_id must match architecture.backend-literal-locality-budget" in summary
    assert payload["violations"] == []


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
    assert observed_count == baseline_count
    assert f"observed={observed_count}" in summary
    assert f"baseline={baseline_count}" in summary
    assert details["baseline_refresh_recommended"] is True
    assert details["baseline_refresh_target_violation_count"] == observed_count
    assert details["baseline_refresh_delta"] == (observed_count - baseline_count)
