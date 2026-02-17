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
        / "check_markdown_locality_reference_coverage.py"
    )


def _write_markdown(
    project_root: Path, relative_path: str, body: str = "content"
) -> None:
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


def test_markdown_locality_rule_uses_expected_rule_id(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Emit the stable rule id from the harness command adapter."""
    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.markdown-locality-reference-coverage"


def test_markdown_locality_rule_passes_for_approved_markdown_locations(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when markdown files remain in approved roots and root exceptions."""
    _write_markdown(tmp_path, "docs/guide.md")
    _write_markdown(tmp_path, "harness/reviewers/prompts/code_simplifier.md")
    _write_markdown(tmp_path, "src/engineeringagent/prompts/templates/loop.md")
    _write_markdown(tmp_path, "src/engineeringagent/scaffold_templates/AGENTS.md")
    _write_markdown(tmp_path, "README.md")
    _write_markdown(tmp_path, "AGENTS.md")
    _write_markdown(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        (
            'PROMPT_TEMPLATE = "src/engineeringagent/prompts/templates/loop.md"\n'
            'README_PATH = "README.md"\n'
            'AGENTS_PATH = "AGENTS.md"\n'
            'REVIEWER_PROMPT_PATH = "harness/reviewers/prompts/code_simplifier.md"\n'
            'SCAFFOLD_PATH = "src/engineeringagent/scaffold_templates/AGENTS.md"\n'
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []


def test_markdown_locality_rule_fails_for_markdown_outside_approved_roots(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail with path:line diagnostics for out-of-policy markdown files."""
    _write_markdown(tmp_path, "CHANGELOG.md")
    _write_markdown(tmp_path, "notes/design.md")
    _write_markdown(tmp_path, "docs/refs.md", "CHANGELOG.md\nnotes/design.md\n")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert violations[0].startswith("CHANGELOG.md:1")
    assert violations[1].startswith("notes/design.md:1")
    assert all(
        "outside approved locality roots" in violation for violation in violations
    )


def test_markdown_locality_rule_ignores_generated_and_cache_directories(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Skip markdown files under ignored directories during locality discovery."""
    _write_markdown(tmp_path, "tmp/notes.md")
    _write_markdown(tmp_path, "dist/output.md")
    _write_markdown(tmp_path, ".venv/docs.md")
    _write_markdown(tmp_path, ".pytest_cache/cache.md")
    _write_markdown(tmp_path, "__pycache__/cache.md")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []


def test_markdown_locality_rule_ignores_tooling_and_vendor_directories(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Skip markdown files under tool-state and vendored dependency directories."""
    _write_markdown(tmp_path, ".opencode/agents/build.md")
    _write_markdown(tmp_path, ".opencode/node_modules/zod/README.md")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []
