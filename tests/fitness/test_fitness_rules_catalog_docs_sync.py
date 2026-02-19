from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast

from engineeringagent.checks import render_fitness_catalog

from tests.helpers.fitness_manifest import write_shell_contract_manifest


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness-functions"
        / "check_fitness_catalog_docs_sync.py"
    )


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


def test_catalog_docs_sync_checker_fails_when_markdown_drifts(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    write_shell_contract_manifest(tmp_path)

    docs_path = tmp_path / "docs" / "fitness-functions" / "rules.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text("stale docs\n", encoding="utf-8")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.fitness-catalog-docs-sync"
    assert result["status"] == "fail"
    assert _violations(result) == [
        "docs/fitness-functions/rules.md:1 differs from `uv run engineeringagent checks catalog --format markdown` output; regenerate with `uv run engineeringagent checks catalog --format markdown --output docs/fitness-functions/rules.md`."
    ]


def test_catalog_docs_sync_checker_passes_when_markdown_matches(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    write_shell_contract_manifest(tmp_path)

    rendered = render_fitness_catalog(tmp_path, format="markdown")
    docs_path = tmp_path / "docs" / "fitness-functions" / "rules.md"
    docs_path.parent.mkdir(parents=True, exist_ok=True)
    docs_path.write_text(rendered + "\n", encoding="utf-8")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)
