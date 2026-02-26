from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import Any, cast

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness-functions"
        / "check_no_pure_wrapper_functions.py"
    )


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
    config_file: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(checker_path), "--config-file", str(config_file)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def _write_file(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_policy(
    project_root: Path,
    *,
    allowlist: list[dict[str, str]] | None = None,
    scan_roots: tuple[str, ...] = ("src/engineeringagent", "harness/fitness-functions"),
) -> Path:
    policy_path = project_root / "policy.yaml"
    payload: dict[str, Any] = {
        "rule_id": "architecture.no-pure-wrapper-functions",
        "scan_roots": list(scan_roots),
        "allowlist": [] if allowlist is None else allowlist,
    }
    policy_path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")
    return policy_path


def test_no_pure_wrapper_rule_flags_deterministic_sorted_violations(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/z_module.py",
        "def z_wrap(value: int) -> int:\n"
        "    return canonical(value)\n",
    )
    _write_file(
        tmp_path,
        "src/engineeringagent/a_module.py",
        "from __future__ import annotations\n\n"
        "def helper(value: int) -> int:\n"
        "    return value + 1\n\n"
        "def a_wrap(value: int) -> int:\n"
        "    return canonical(value)\n",
    )
    _write_file(
        tmp_path,
        "harness/fitness-functions/wrapper.py",
        "from __future__ import annotations\n\n"
        "async def forward_async(*args: object, **kwargs: object) -> object:\n"
        "    return await canonical(*args, **kwargs)\n",
    )

    policy_path = _write_policy(tmp_path)
    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_path,
    )
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.no-pure-wrapper-functions"
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert any("src/engineeringagent/a_module.py:6" in item for item in violations)
    assert any("src/engineeringagent/z_module.py:1" in item for item in violations)
    assert any("harness/fitness-functions/wrapper.py:3" in item for item in violations)
    assert all("remediation order:" in item for item in violations)


def test_no_pure_wrapper_rule_honors_allowlist_exceptions(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    (tmp_path / "harness" / "fitness-functions").mkdir(parents=True, exist_ok=True)
    _write_file(
        tmp_path,
        "src/engineeringagent/allowed.py",
        "def allowed_wrapper(value: int) -> int:\n"
        "    return canonical(value)\n",
    )
    _write_file(
        tmp_path,
        "src/engineeringagent/blocked.py",
        "def blocked_wrapper(value: int) -> int:\n"
        "    return canonical(value)\n",
    )

    policy_path = _write_policy(
        tmp_path,
        allowlist=[
            {
                "path": "src/engineeringagent/allowed.py",
                "function": "allowed_wrapper",
                "rationale": "temporary boundary while moving ownership",
                "remediation": "remove wrapper after canonical ownership move",
            }
        ],
    )
    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_path,
    )
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert not any("allowed.py" in item for item in violations)
    assert any("blocked.py" in item for item in violations)


def test_no_pure_wrapper_rule_flags_keyword_identity_forwarding_for_positional_parameters(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/keyword_wrapper.py",
        "def keyword_wrapper(value: int, count: int) -> int:\n"
        "    return canonical(value=value, count=count)\n",
    )
    _write_file(
        tmp_path,
        "harness/fitness-functions/helper.py",
        "def helper() -> None:\n"
        "    return None\n",
    )

    policy_path = _write_policy(tmp_path)
    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_path,
    )
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "src/engineeringagent/keyword_wrapper.py:1 pure wrapper function 'keyword_wrapper'"
        in item
        for item in violations
    )


def test_no_pure_wrapper_rule_passes_when_no_wrappers_found(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/non_wrapper.py",
        "def keep_logic(value: int) -> int:\n"
        "    transformed = value + 2\n"
        "    return canonical(transformed)\n",
    )
    _write_file(
        tmp_path,
        "harness/fitness-functions/helper.py",
        "def format_message(value: str) -> str:\n"
        "    return f'hello {value}'\n",
    )

    policy_path = _write_policy(tmp_path)
    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_path,
    )

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []


def test_no_pure_wrapper_rule_fails_on_invalid_allowlist_entry(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/example.py",
        "def wrapper(value: int) -> int:\n"
        "    return canonical(value)\n",
    )

    policy_path = _write_policy(
        tmp_path,
        allowlist=[
            {
                "path": "src/engineeringagent/example.py",
                "function": "wrapper",
            }
        ],
    )
    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_path,
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "config key 'allowlist[0].rationale' must be a non-empty string"
    ]


def test_no_pure_wrapper_rule_fails_without_allowlist_remediation_note(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/example.py",
        "def wrapper(value: int) -> int:\n"
        "    return canonical(value)\n",
    )

    policy_path = _write_policy(
        tmp_path,
        allowlist=[
            {
                "path": "src/engineeringagent/example.py",
                "function": "wrapper",
                "rationale": "temporary exception for migration",
            }
        ],
    )
    proc, result = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_path,
    )

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert _violations(result) == [
        "config key 'allowlist[0].remediation' must be a non-empty string"
    ]
