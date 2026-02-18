from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness-functions"
        / "check_retry_feedback_no_truncation.py"
    )


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


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


def test_retry_feedback_no_truncation_checker_emits_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        "def inject_retry_feedback(prompt: str, hook_feedback: str | None) -> str:\n"
        "    return prompt\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.retry-feedback-no-truncation"


def test_retry_feedback_no_truncation_rule_fails_on_hook_feedback_slice(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        "def inject_retry_feedback(prompt: str, hook_feedback: str | None) -> str:\n"
        "    if hook_feedback:\n"
        "        return prompt + hook_feedback[:8000]\n"
        "    return prompt\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any("slices hook_feedback" in violation for violation in violations)


def test_retry_feedback_no_truncation_rule_fails_on_normalized_feedback_slice(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        "def _normalize_retry_feedback(hook_feedback: str) -> str:\n"
        "    return hook_feedback\n"
        "\n"
        "def inject_retry_feedback(prompt: str, hook_feedback: str | None) -> str:\n"
        "    if not hook_feedback:\n"
        "        return prompt\n"
        "    return prompt + _normalize_retry_feedback(hook_feedback)[:8000]\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "slices normalized retry feedback" in violation for violation in violations
    )


def test_retry_feedback_no_truncation_rule_fails_on_truncate_helper_call(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        "def _truncate_feedback(value: str) -> str:\n"
        "    return value[:8000]\n"
        "\n"
        "def inject_retry_feedback(prompt: str, hook_feedback: str | None) -> str:\n"
        "    if hook_feedback:\n"
        "        return prompt + _truncate_feedback(hook_feedback)\n"
        "    return prompt\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any("calls _truncate_feedback" in violation for violation in violations)


def test_retry_feedback_no_truncation_rule_passes_without_slicing(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_module(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        "def _normalize_retry_feedback(hook_feedback: str) -> str:\n"
        "    return hook_feedback\n"
        "\n"
        "def inject_retry_feedback(prompt: str, hook_feedback: str | None) -> str:\n"
        "    if not hook_feedback:\n"
        "        return prompt\n"
        "    return prompt + _normalize_retry_feedback(hook_feedback)\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)
