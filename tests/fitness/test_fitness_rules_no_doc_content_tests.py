from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import cast

from engineeringagent.fitness.registry import build_rule_catalog


def _script_path(repo_root: Path) -> Path:
    return repo_root / "harness" / "fitness-functions" / "check_no_doc_content_tests.py"


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


def _write_test_module(project_root: Path, *, relative_path: str, content: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


def test_manifest_includes_no_doc_content_tests_rule(repo_root: Path) -> None:
    """Ensure the rule is present in the catalog."""
    catalog = build_rule_catalog(repo_root)
    definition = next(
        item
        for item in catalog
        if item.metadata.rule_id == "architecture.no-doc-content-tests"
    )
    assert definition.command == (
        "uv",
        "run",
        "python",
        "harness/fitness-functions/check_no_doc_content_tests.py",
    )


def test_checker_flags_wrapper_helper_calls_with_constant_doc_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Flag wrapper reads when docs path is a string literal."""
    _write_test_module(
        tmp_path,
        relative_path="tests/test_doc_content_violation.py",
        content="\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def _read(repo_root: Path, relpath: str) -> str:",
                '    return (repo_root / relpath).read_text(encoding="utf-8")',
                "",
                "def test_reads_docs_via_wrapper(repo_root: Path) -> None:",
                '    _read(repo_root, "docs/guide.md")',
                "",
            ]
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["rule_id"] == "architecture.no-doc-content-tests"
    assert result["status"] == "fail"
    assert violations == sorted(violations)
    assert any("docs/guide.md" in violation for violation in violations)


def test_checker_flags_wrapper_helper_calls_with_variable_doc_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Flag wrapper reads when docs path flows through a variable."""
    _write_test_module(
        tmp_path,
        relative_path="tests/test_doc_content_violation.py",
        content="\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def _read(repo_root: Path, relpath: str) -> str:",
                '    return (repo_root / relpath).read_text(encoding="utf-8")',
                "",
                "def test_reads_docs_via_wrapper(repo_root: Path) -> None:",
                '    doc_path = "docs/guide.md"',
                "    _read(repo_root, doc_path)",
                "",
            ]
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    violations = _violations(result)

    assert proc.returncode == 0
    assert result["status"] == "fail"
    assert any("docs/guide.md" in violation for violation in violations)


def test_checker_allows_generated_rules_markdown_sync_reads(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allowlist reads used for rules markdown sync checks."""
    _write_test_module(
        tmp_path,
        relative_path="tests/test_rules_sync.py",
        content="\n".join(
            [
                "from __future__ import annotations",
                "",
                "from pathlib import Path",
                "",
                "def _read(repo_root: Path, relpath: str) -> str:",
                '    return (repo_root / relpath).read_text(encoding="utf-8")',
                "",
                "def test_rules_markdown_sync(repo_root: Path) -> None:",
                '    _read(repo_root, "docs/fitness-functions/rules.md")',
                "",
            ]
        ),
    )

    proc, result = _run_checker(tmp_path, checker_path=_script_path(repo_root))
    assert proc.returncode == 0
    assert result["status"] == "pass"
    assert _violations(result) == []
