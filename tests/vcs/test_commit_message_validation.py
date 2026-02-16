from __future__ import annotations

import ast
import importlib.util
import re
import subprocess
import sys
from pathlib import Path

import pytest


def _repo_root(pytestconfig: pytest.Config) -> Path:
    return Path(pytestconfig.rootpath)


def _run_git(
    repo: Path, *args: str, check: bool = True
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=repo,
        check=check,
        capture_output=True,
        text=True,
    )


def _validator_script(pytestconfig: pytest.Config) -> Path:
    repo_root = _repo_root(pytestconfig)
    return repo_root / "harness" / "fitness-functions" / "validate_commit_messages.py"


def _run_validator(
    pytestconfig: pytest.Config,
    *args: str,
    cwd: Path | None = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        [sys.executable, str(_validator_script(pytestconfig)), *args],
        cwd=cwd,
        capture_output=True,
        text=True,
    )


def _init_repo(repo: Path) -> None:
    repo.mkdir(parents=True, exist_ok=True)
    _run_git(repo, "init")
    _run_git(repo, "config", "user.name", "test")
    _run_git(repo, "config", "user.email", "test@example.com")


def test_tests_do_not_import_engineeringagent_commit_messages(
    pytestconfig: pytest.Config,
) -> None:
    repo_root = _repo_root(pytestconfig)
    tests_root = repo_root / "tests"

    def _fail(path: Path) -> None:
        pytest.fail(f"{path}: tests must not import engineeringagent.commit_messages")

    for path in sorted(tests_root.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        tree = ast.parse(text)

        for node in ast.walk(tree):
            if (
                isinstance(node, ast.ImportFrom)
                and node.module == "engineeringagent.commit_messages"
            ):
                _fail(path)
            if isinstance(node, ast.ImportFrom) and node.module == "engineeringagent":
                for alias in node.names:
                    if alias.name == "commit_messages":
                        _fail(path)
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "engineeringagent.commit_messages":
                        _fail(path)


def test_commit_subject_pattern_generated_from_allowed_types(
    pytestconfig: pytest.Config,
) -> None:
    repo_root = _repo_root(pytestconfig)
    module_path = repo_root / "harness" / "fitness-functions" / "commit_messages.py"
    spec = importlib.util.spec_from_file_location(
        "harness_commit_messages", module_path
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)

    allowed = "|".join(re.escape(t) for t in module.ALLOWED_COMMIT_TYPES)
    expected = rf"^(?:{allowed}): [^\n]+$"
    assert module.COMMIT_SUBJECT_PATTERN.pattern == expected


def test_validate_commit_subject_accepts_allowed_format(
    pytestconfig: pytest.Config,
    tmp_path: Path,
) -> None:
    commit_file = tmp_path / "COMMIT_EDITMSG"
    for subject in [
        "feat: add deterministic selection",
        "fix: prevent flaky loop retries",
        "spec: enforce metadata contract",
    ]:
        commit_file.write_text(subject + "\n", encoding="utf-8")
        proc = _run_validator(pytestconfig, "--commit-msg-file", str(commit_file))
        assert proc.returncode == 0
        assert "commit message validation: ok" in proc.stdout


def test_validate_commit_subject_rejects_invalid_prefix(
    pytestconfig: pytest.Config,
    tmp_path: Path,
) -> None:
    commit_file = tmp_path / "COMMIT_EDITMSG"
    commit_file.write_text("refactor: improve readability\n", encoding="utf-8")

    proc = _run_validator(pytestconfig, "--commit-msg-file", str(commit_file))
    assert proc.returncode == 1
    assert "commit message validation failed:" in proc.stdout
    assert "type: summary" in proc.stdout
    assert "subject: refactor: improve readability" in proc.stdout


def test_commit_msg_file_mode_skips_comments(
    pytestconfig: pytest.Config,
    tmp_path: Path,
) -> None:
    commit_file = tmp_path / "COMMIT_EDITMSG"
    commit_file.write_text(
        "\n# Please enter the commit message\nfeat: add commit hook\n\nbody\n",
        encoding="utf-8",
    )

    proc = _run_validator(pytestconfig, "--commit-msg-file", str(commit_file))
    assert proc.returncode == 0
    assert "commit message validation: ok" in proc.stdout


def test_commit_range_mode_reports_deterministic_errors(
    pytestconfig: pytest.Config,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    (repo / "notes.txt").write_text("line 1\n", encoding="utf-8")
    _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-m", "feat: add commit policy")

    (repo / "notes.txt").write_text("line 2\n", encoding="utf-8")
    _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-m", "bad message")

    (repo / "notes.txt").write_text("line 3\n", encoding="utf-8")
    _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-m", "chore: tighten hooks")

    (repo / "notes.txt").write_text("line 4\n", encoding="utf-8")
    _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-m", "refactor: invalid prefix")

    proc = _run_validator(
        pytestconfig,
        "--project-root",
        str(repo),
        "--commit-range",
        "HEAD~3..HEAD",
    )
    assert proc.returncode == 1
    assert proc.stdout.splitlines() == [
        "commit[1] `refactor: invalid prefix`: subject must match `type: summary` with allowed types [feat, fix, spec, docs, chore, test]",
        "commit[3] `bad message`: subject must match `type: summary` with allowed types [feat, fix, spec, docs, chore, test]",
    ]


def test_commit_range_mode_ok_for_valid_subjects(
    pytestconfig: pytest.Config,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    (repo / "notes.txt").write_text("line 1\n", encoding="utf-8")
    _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-m", "feat: add notes")

    (repo / "notes.txt").write_text("line 2\n", encoding="utf-8")
    _run_git(repo, "add", "notes.txt")
    _run_git(repo, "commit", "-m", "docs: update notes")

    proc = _run_validator(
        pytestconfig,
        "--project-root",
        str(repo),
        "--commit-range",
        "HEAD~1..HEAD",
    )
    assert proc.returncode == 0
    assert "commit range validation: ok" in proc.stdout


def test_commit_range_mode_raises_for_invalid_range(
    pytestconfig: pytest.Config,
    tmp_path: Path,
) -> None:
    repo = tmp_path / "repo"
    _init_repo(repo)

    proc = _run_validator(
        pytestconfig,
        "--project-root",
        str(repo),
        "--commit-range",
        "missing-range",
    )
    assert proc.returncode == 1
    assert "commit range validation failed:" in proc.stdout
