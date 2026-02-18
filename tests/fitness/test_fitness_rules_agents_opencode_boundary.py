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
        / "check_agents_opencode_boundary.py"
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


def test_agents_opencode_boundary_fitness_rule_registered() -> None:
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)

    rules = manifest.get("rules")
    assert isinstance(rules, list)

    matching: list[dict[str, object]] = []
    for rule in rules:
        if not isinstance(rule, dict):
            continue
        if rule.get("rule_id") == "architecture.agents-opencode-boundary":
            matching.append(rule)

    assert len(matching) == 1

    command = matching[0].get("command")
    assert isinstance(command, list)
    assert "harness/fitness-functions/check_agents_opencode_boundary.py" in command

    assert Path("harness/fitness-functions/check_agents_opencode_boundary.py").exists()


def test_agents_opencode_boundary_fitness_rule_passes_clean_repo() -> None:
    proc = subprocess.run(
        [
            sys.executable,
            "harness/fitness-functions/check_agents_opencode_boundary.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0

    payload = json.loads(proc.stdout)
    assert payload["rule_id"] == "architecture.agents-opencode-boundary"
    assert payload["status"] == "pass"


def test_agents_opencode_boundary_rule_reports_from_import_violations(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/foo.py",
        "\n".join(
            [
                "from engineeringagent.agents.backends.opencode import client",
                "from engineeringagent.opencode import client as legacy_client",
                "",
                "def noop() -> None:",
                "    return",
            ]
        ),
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.agents-opencode-boundary"
    assert payload["status"] == "fail"

    violations = payload.get("violations")
    assert isinstance(violations, list)
    assert violations == sorted(violations)
    assert len(violations) == 2
    assert any(
        "src/engineeringagent/foo.py:1:" in violation
        and "imports opencode backend package" in violation
        for violation in violations
    ), violations
    assert any(
        "src/engineeringagent/foo.py:2:" in violation
        and "imports legacy opencode package" in violation
        for violation in violations
    ), violations
