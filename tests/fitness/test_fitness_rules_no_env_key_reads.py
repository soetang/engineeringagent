from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from engineeringagent.fitness.registry import build_rule_catalog


def _script_path(repo_root: Path) -> Path:
    return repo_root / "harness" / "fitness-functions" / "check_no_env_key_reads.py"


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


def _write_module(project_root: Path, *, relative_path: str, content: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_manifest_includes_no_env_key_reads_rule(repo_root: Path) -> None:
    catalog = build_rule_catalog(repo_root)
    definition = next(
        item
        for item in catalog
        if item.metadata.rule_id == "architecture.no-env-key-reads"
    )
    assert definition.command == (
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_no_env_key_reads.py",
    )


def test_checker_flags_os_getenv_and_environ_get(
    tmp_path: Path, repo_root: Path
) -> None:
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/forbidden_env_read.py",
        content="\n".join(
            [
                "from __future__ import annotations",
                "",
                "import os",
                "",
                "def read_env() -> None:",
                "    _ = os.getenv('SOME_KEY')",
                "    _ = os.environ.get('OTHER_KEY')",
                "",
            ]
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.no-env-key-reads"
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert any("os.getenv" in violation for violation in violations)
    assert any("os.environ.get" in violation for violation in violations)


def test_checker_flags_environ_subscript_and_membership(
    tmp_path: Path, repo_root: Path
) -> None:
    _write_module(
        tmp_path,
        relative_path="tests/test_forbidden_env_access.py",
        content="\n".join(
            [
                "from __future__ import annotations",
                "",
                "import os",
                "",
                "def test_forbidden() -> None:",
                "    _ = os.environ['HOME']",
                "    assert 'PATH' in os.environ",
                "",
            ]
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any("os.environ[" in violation for violation in violations)
    assert any("in os.environ" in violation for violation in violations)


def test_checker_allows_os_environ_copy(tmp_path: Path, repo_root: Path) -> None:
    _write_module(
        tmp_path,
        relative_path="harness/fitness-functions/allowed_env_passthrough.py",
        content="\n".join(
            [
                "from __future__ import annotations",
                "",
                "import os",
                "",
                "def build_env() -> dict[str, str]:",
                "    env = os.environ.copy()",
                "    env['X'] = '1'",
                "    return env",
                "",
            ]
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []


def test_checker_flags_from_os_import_aliases(tmp_path: Path, repo_root: Path) -> None:
    _write_module(
        tmp_path,
        relative_path="src/engineeringagent/forbidden_env_alias.py",
        content="\n".join(
            [
                "from __future__ import annotations",
                "",
                "from os import environ, getenv as get_env",
                "",
                "def read_env() -> None:",
                "    _ = get_env('SOME_KEY')",
                "    _ = environ.get('OTHER_KEY')",
                "",
            ]
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any("getenv" in violation for violation in violations)
    assert any("environ.get" in violation for violation in violations)
