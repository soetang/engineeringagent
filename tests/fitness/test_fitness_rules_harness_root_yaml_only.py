from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root / "harness" / "fitness-functions" / "check_harness_root_yaml_only.py"
    )


def _write_file(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")


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


def test_fails_for_non_yaml_regular_files_at_harness_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Fail when harness root contains regular files that are not YAML manifests."""
    _write_file(
        tmp_path / "harness/checks.yaml", "contract_version: '1.0'\nchecks: {}\n"
    )
    _write_file(tmp_path / "harness/checks.local.yml", "checks: {}\n")
    _write_file(tmp_path / "harness/validate_yaml.py", "print('bad')\n")
    _write_file(tmp_path / "harness/notes.txt", "bad\n")
    _write_file(
        tmp_path / "harness/fitness-functions/validate_yaml.py", "print('ok')\n"
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    assert payload["severity"] == "error"
    assert payload["rule_id"] == "architecture.harness-root-yaml-only"
    assert payload["violations"] == [
        (
            "harness/notes.txt:1 non-YAML regular file at harness root; "
            "move executable/policy files under harness/fitness-functions or another "
            "harness subdirectory."
        ),
        (
            "harness/validate_yaml.py:1 non-YAML regular file at harness root; "
            "move executable/policy files under harness/fitness-functions or another "
            "harness subdirectory."
        ),
    ]


def test_passes_when_harness_root_contains_only_yaml_files(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Pass when harness root has YAML files and nested directories only."""
    _write_file(
        tmp_path / "harness/checks.yaml", "contract_version: '1.0'\nchecks: {}\n"
    )
    _write_file(tmp_path / "harness/checks.local.yml", "checks: {}\n")
    _write_file(
        tmp_path / "harness/fitness-functions/validate_yaml.py", "print('ok')\n"
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert not payload["violations"]
