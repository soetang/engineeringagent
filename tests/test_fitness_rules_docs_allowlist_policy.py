from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast

import yaml

from engineeringagent.fitness.registry import build_rule_catalog


SCRIPT_PATH = (
    Path(__file__).resolve().parents[1]
    / "harness"
    / "fitness-functions"
    / "check_docs_allowlist_policy.py"
)


def _violations(result: dict[str, object]) -> list[str]:
    return cast(list[str], result["violations"])


def _run_checker(
    project_root: Path,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def _write_policy(
    project_root: Path,
    *,
    docs_root: str,
    human_docs: list[str],
    agent_docs: list[str],
) -> None:
    path = project_root / "harness" / "scaffold_policy.yaml"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "docs_root": docs_root,
                "human_docs": human_docs,
                "agent_docs": agent_docs,
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def _write_md(
    project_root: Path, *, relative_path: str, content: str = "# ok\n"
) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_manifest_includes_docs_allowlist_policy_rule() -> None:
    """Keep the docs allowlist policy rule declared in the default manifest."""
    project_root = Path(__file__).resolve().parents[1]
    catalog = build_rule_catalog(project_root)

    definition = next(
        item
        for item in catalog
        if item.metadata.rule_id == "architecture.docs-allowlist-policy"
    )
    assert definition.command == (
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_docs_allowlist_policy.py",
    )


def test_docs_allowlist_checker_fails_when_doc_missing_from_both_lists(
    tmp_path: Path,
) -> None:
    _write_md(tmp_path, relative_path="docs/guide.md")
    _write_policy(tmp_path, docs_root="docs", human_docs=[], agent_docs=[])

    proc, result = _run_checker(tmp_path)
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.docs-allowlist-policy"
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert any("docs/guide.md" in violation for violation in violations)


def test_docs_allowlist_checker_fails_when_doc_in_both_lists(tmp_path: Path) -> None:
    _write_md(tmp_path, relative_path="docs/guide.md")
    _write_policy(
        tmp_path,
        docs_root="docs",
        human_docs=["docs/guide.md"],
        agent_docs=["docs/guide.md"],
    )

    proc, result = _run_checker(tmp_path)
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any(
        "both human_docs and agent_docs" in violation for violation in violations
    )


def test_docs_allowlist_checker_passes_when_all_docs_are_classified(
    tmp_path: Path,
) -> None:
    _write_md(tmp_path, relative_path="docs/guide.md")
    _write_md(tmp_path, relative_path="docs/agents.md")
    _write_md(tmp_path, relative_path="docs/spec/ignored.md")
    _write_policy(
        tmp_path,
        docs_root="docs",
        human_docs=["docs/guide.md"],
        agent_docs=["docs/agents.md"],
    )

    proc, result = _run_checker(tmp_path)

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []


def test_docs_allowlist_checker_passes_with_empty_human_docs_flow_list(
    tmp_path: Path,
) -> None:
    _write_md(tmp_path, relative_path="docs/references/agent.md")
    _write_policy(
        tmp_path,
        docs_root="docs",
        human_docs=[],
        agent_docs=["docs/references/agent.md"],
    )

    proc, result = _run_checker(tmp_path)
    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []
