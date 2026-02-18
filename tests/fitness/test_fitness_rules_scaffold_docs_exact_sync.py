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
        / "check_scaffold_docs_exact_sync.py"
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


def _write_policy(project_root: Path, *, docs_path: str) -> None:
    path = project_root / "harness" / "scaffold_policy.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "docs_root": "docs",
                "exact_sync": [
                    {
                        "docs_path": docs_path,
                        "template_name": "reference.spec-writing-llms.md",
                    }
                ],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def _write_docs_file(project_root: Path, *, relative_path: str, content: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def _write_template_file(project_root: Path, *, name: str, content: str) -> None:
    path = project_root / "src" / "engineeringagent" / "scaffold_templates" / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_exact_sync_checker_fails_when_docs_and_template_differ(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail with deterministic diagnostics when configured pairs drift."""
    _write_policy(tmp_path, docs_path="references/spec-writing-llms.md")
    _write_docs_file(
        tmp_path,
        relative_path="docs/references/spec-writing-llms.md",
        content="canonical\n",
    )
    _write_template_file(
        tmp_path,
        name="reference.spec-writing-llms.md",
        content="template\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.scaffold-docs-exact-sync"
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert any(
        "docs/references/spec-writing-llms.md" in violation
        and "src/engineeringagent/scaffold_templates/reference.spec-writing-llms.md"
        in violation
        for violation in violations
    )


def test_exact_sync_checker_passes_when_docs_and_template_match(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when configured docs and templates are byte-for-byte identical."""
    content = "same bytes\n"
    _write_policy(tmp_path, docs_path="references/spec-writing-llms.md")
    _write_docs_file(
        tmp_path,
        relative_path="docs/references/spec-writing-llms.md",
        content=content,
    )
    _write_template_file(
        tmp_path,
        name="reference.spec-writing-llms.md",
        content=content,
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)


def test_exact_sync_checker_fails_when_configured_docs_file_is_missing(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when the policy points at missing docs/template paths."""
    _write_policy(tmp_path, docs_path="references/spec-writing-llms.md")
    _write_template_file(
        tmp_path,
        name="reference.spec-writing-llms.md",
        content="ok\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any("missing" in violation for violation in violations)
