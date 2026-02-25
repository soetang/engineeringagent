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
        / "fitness-functions"
        / "check_loop_checks_result_boundary.py"
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


def test_loop_checks_result_boundary_rule_configuration() -> None:
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))

    rules = manifest["rules"]
    configured = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.loop-checks-result-boundary"
    ]

    assert len(configured) == 1
    rule = configured[0]
    assert rule["adapter"] == "command"
    assert rule["severity"] == "error"
    assert rule["command"] == [
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_loop_checks_result_boundary.py",
    ]


def test_loop_checks_result_boundary_rule_passes_without_checks_internal_parsing(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_loop_modules(
        tmp_path,
        phases_body="\n".join(
            [
                "from __future__ import annotations",
                "",
                "def run_gate_phase(result) -> str:",
                "    if result.ok:",
                "        return result.output",
                "    return result.prompt_feedback or result.output",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.loop-checks-result-boundary"
    assert payload["status"] == "pass"
    assert not _violations(payload)


def test_loop_checks_result_boundary_rule_fails_on_group_branching_and_payload_parsing(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_loop_modules(
        tmp_path,
        phases_body="\n".join(
            [
                "from __future__ import annotations",
                "",
                "def run_gate_phase(result) -> str:",
                "    if result.failed_group == 'commands':",
                "        return result.failed_payload['reason']",
                "    return result.decisions[0]['check_type']",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    violations = _violations(payload)
    assert any("'failed_group'" in violation for violation in violations)
    assert any("'failed_payload'" in violation for violation in violations)
    assert any("'check_type'" in violation for violation in violations)
