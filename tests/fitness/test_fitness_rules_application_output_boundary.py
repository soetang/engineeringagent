from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_application_output_boundary.py"
    )


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


def _violations(payload: dict[str, object]) -> list[str]:
    return cast(list[str], payload["violations"])


def test_checker_flags_direct_print_calls_in_application_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when an application module prints directly to stdout."""
    module_path = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "implementation_step.py"
    )
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text("print('oops')\n", encoding="utf-8")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.application-output-boundary"
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/implementation_step.py:1 application modules must not print directly; return data or emit through injected runtime/presentation callbacks"
    ]


def test_checker_allows_application_modules_without_direct_print_calls(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when application modules only return data and avoid print calls."""
    module_path = (
        tmp_path / "src" / "engineeringagent" / "application" / "prompt_builder.py"
    )
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(
        "\n".join(
            [
                "def render() -> str:",
                "    return 'prompt'",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []
