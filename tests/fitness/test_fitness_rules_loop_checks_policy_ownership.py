from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "check_loop_checks_policy_ownership.py"
    )


def _write_loop_modules(
    project_root: Path,
    *,
    phases_body: str,
    loop_body: str = "from __future__ import annotations\n",
) -> None:
    phases_path = project_root / "src/engineeringagent/loop_runtime/phases.py"
    phases_path.parent.mkdir(parents=True, exist_ok=True)
    phases_path.write_text(phases_body, encoding="utf-8")

    loop_path = project_root / "src/engineeringagent/loop.py"
    loop_path.parent.mkdir(parents=True, exist_ok=True)
    loop_path.write_text(loop_body, encoding="utf-8")


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


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def test_loop_checks_policy_ownership_rule_configuration() -> None:
    manifest_path = Path("harness/fitness_functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rules = manifest["rules"]
    configured = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.loop-checks-policy-ownership"
    ]

    assert len(configured) == 1
    rule = configured[0]
    assert rule["adapter"] == "command"
    assert rule["severity"] == "error"
    assert rule["command"] == [
        "uv",
        "run",
        "python",
        "harness/fitness_functions/check_loop_checks_policy_ownership.py",
    ]


def test_loop_checks_policy_ownership_rule_passes_when_loop_delegates_by_phase_only(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_loop_modules(
        tmp_path,
        phases_body="\n".join(
            [
                "from __future__ import annotations",
                "",
                "from engineeringagent.checks import run_checks",
                "",
                "def run_phase(project_root, phase):",
                "    return run_checks(project_root, phase=phase)",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.loop-checks-policy-ownership"
    assert payload["status"] == "pass"
    assert not _violations(payload)


def test_loop_checks_policy_ownership_rule_fails_on_group_constants_and_explicit_checks(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_loop_modules(
        tmp_path,
        phases_body="\n".join(
            [
                "from __future__ import annotations",
                "",
                "from engineeringagent.checks import run_checks",
                "from engineeringagent.specs import HarnessCheckPhase",
                "",
                "_GATE_CHECK_GROUPS_BY_PHASE = {",
                "    HarnessCheckPhase.ITERATION_END: ('validate', 'commands', 'fitness'),",
                "}",
                "",
                "def run_phase(project_root, phase):",
                "    return run_checks(",
                "        project_root,",
                "        phase=phase,",
                "        checks=['validate', 'commands'],",
                "        selection_profile='loop_gate',",
                "    )",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    violations = _violations(payload)
    assert any("defines loop-owned checks group policy" in violation for violation in violations)
    assert any("passes explicit checks policy" in violation for violation in violations)
    assert any("passes selection profile" in violation for violation in violations)


def test_loop_checks_policy_ownership_rule_fails_on_empty_checks_list(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_loop_modules(
        tmp_path,
        phases_body="\n".join(
            [
                "from __future__ import annotations",
                "",
                "from engineeringagent.checks import run_checks",
                "from engineeringagent.specs import HarnessCheckPhase",
                "",
                "def run_phase(project_root, phase):",
                "    return run_checks(project_root, phase=phase, checks=[])",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    violations = _violations(payload)
    assert any("passes explicit checks policy" in violation for violation in violations)
