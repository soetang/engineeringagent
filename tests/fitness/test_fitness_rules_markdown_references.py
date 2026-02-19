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


def _write_file(project_root: Path, relative_path: str, body: str = "content") -> None:
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


def test_markdown_reference_coverage_passes_with_non_self_reference(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(tmp_path, "src/engineeringagent/prompts/templates/loop.md")
    _write_file(
        tmp_path,
        "src/engineeringagent/prompts/renderer.py",
        'TEMPLATE_PATH = "src/engineeringagent/prompts/templates/loop.md"\n',
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)


def test_markdown_reference_coverage_passes_for_reviewer_prompt_with_reference(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(tmp_path, "harness/reviewers/prompts/code_simplifier.md")
    _write_file(
        tmp_path,
        "src/engineeringagent/init_scaffold.py",
        'PROMPT_PATH = "harness/reviewers/prompts/code_simplifier.md"\n',
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)


def test_markdown_reference_coverage_fails_when_non_doc_markdown_is_unreferenced(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(tmp_path, "README.md")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert violations == [
        "README.md:1 markdown file outside docs/ has no in-repo non-self reference; add at least one deterministic path reference from another repository file."
    ]


def test_markdown_reference_coverage_requires_non_self_reference(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/scaffold_templates/AGENTS.md",
        "See src/engineeringagent/scaffold_templates/AGENTS.md\n",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert violations == [
        "src/engineeringagent/scaffold_templates/AGENTS.md:1 markdown file outside docs/ has no in-repo non-self reference; add at least one deterministic path reference from another repository file."
    ]


def test_markdown_reference_coverage_skips_docs_markdown(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(tmp_path, "docs/reference.md")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)


def test_markdown_reference_coverage_ignores_references_from_ignored_directories(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(tmp_path, "README.md")
    _write_file(tmp_path, "tmp/references.txt", "README.md\n")

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert violations == [
        "README.md:1 markdown file outside docs/ has no in-repo non-self reference; add at least one deterministic path reference from another repository file."
    ]


def test_markdown_reference_coverage_exempts_backend_scaffold_markdown(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/agents/backends/opencode/scaffold_templates/agent.engineeringagent.md",
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert not _violations(result)
