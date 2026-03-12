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
        / "check_application_filesystem_boundary.py"
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


def test_checker_flags_direct_filesystem_mutations_in_application_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when an application module mutates files directly."""
    module_path = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "workspace"
        / "init_service.py"
    )
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "",
                "def mutate(root: Path) -> None:",
                "    (root / 'AGENTS.md').rename(root / 'AGENTS.user.md')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.application-filesystem-boundary"
    assert payload["status"] == "fail"
    assert _violations(payload) == [
        "src/engineeringagent/application/workspace/init_service.py:4 application modules must delegate filesystem mutations through ports or injected dependencies; found `rename()`"
    ]


def test_checker_allows_non_mutating_application_modules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when application modules only compute values."""
    module_path = (
        tmp_path
        / "src"
        / "engineeringagent"
        / "application"
        / "prompt_builder.py"
    )
    module_path.parent.mkdir(parents=True, exist_ok=True)
    module_path.write_text(
        "\n".join(
            [
                "from pathlib import Path",
                "",
                "def render(path: Path) -> str:",
                "    return str(path.parent / 'plan.md')",
                "",
            ]
        ),
        encoding="utf-8",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert _violations(payload) == []
