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
        / "check_scaffold_template_agents_doc_links.py"
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


def _write_policy(project_root: Path, *, scaffold_docs: list[str]) -> None:
    path = project_root / "harness" / "scaffold_policy.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "docs_root": "docs",
                "scaffold_docs": scaffold_docs,
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def _write_scaffold_agents(project_root: Path, *, content: str) -> None:
    path = (
        project_root / "src" / "engineeringagent" / "scaffold_templates" / "AGENTS.md"
    )
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_agents_link_checker_fails_when_scaffold_doc_is_missing_from_template(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail with deterministic diagnostics when scaffold docs are not linked."""
    expected = [
        "docs/references/docs-architecture-llms.md",
        "docs/references/workflow-llms.md",
        "docs/references/spec-writing-llms.md",
    ]
    _write_policy(tmp_path, scaffold_docs=expected)
    _write_scaffold_agents(
        tmp_path,
        content=(
            "# AGENTS\n\n"
            "- `docs/references/docs-architecture-llms.md`: ok\n"
            "- `docs/references/workflow-llms.md`: ok\n"
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.scaffold-template-agents-doc-links"
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert any(
        "docs/references/spec-writing-llms.md" in violation for violation in violations
    )
    assert any(
        "src/engineeringagent/scaffold_templates/AGENTS.md" in violation
        for violation in violations
    )


def test_agents_link_checker_passes_when_all_scaffold_docs_are_linked(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when every scaffolded doc is linked with a description."""
    expected = [
        "docs/references/docs-architecture-llms.md",
        "docs/references/workflow-llms.md",
        "docs/references/spec-writing-llms.md",
    ]
    _write_policy(tmp_path, scaffold_docs=expected)
    _write_scaffold_agents(
        tmp_path,
        content=(
            "# AGENTS\n\n"
            "- `docs/references/docs-architecture-llms.md`: When working on docs layout.\n"
            "- `docs/references/workflow-llms.md`: Before running loop work.\n"
            "- `docs/references/spec-writing-llms.md`: When drafting feature specs.\n"
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)
