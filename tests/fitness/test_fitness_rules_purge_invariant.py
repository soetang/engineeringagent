from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
        / "check_purge_invariant.py"
    )


def _run_git(project_root: Path, *args: str) -> None:
    proc = subprocess.run(
        ["git", *args],
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr


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


def test_purge_invariant_rule_registered() -> None:
    """Manifest registration points at the purge-invariant checker script."""
    manifest_path = Path("harness/fitness_functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)

    rules = manifest.get("rules")
    assert isinstance(rules, list)

    matching = [
        rule
        for rule in rules
        if isinstance(rule, dict) and rule.get("rule_id") == "quality.purge-invariant"
    ]

    assert len(matching) == 1
    command = matching[0].get("command")
    assert isinstance(command, list)
    assert "harness/fitness_functions/rules/check_purge_invariant.py" in command
    assert Path("harness/fitness_functions/rules/check_purge_invariant.py").exists()


def test_purge_invariant_rule_reports_tracked_violations_and_exclusions(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Tracked files fail while excluded progress artifacts stay ignored."""
    _run_git(tmp_path, "init")

    removed_reviewer_id = "_".join(["readme", "process"])
    removed_mode = "_".join(["clean", "room", "readme", "cli"])

    (tmp_path / "active.txt").write_text(
        f"{removed_reviewer_id}\n{removed_mode}\n",
        encoding="utf-8",
    )
    _run_git(tmp_path, "add", "active.txt")

    excluded_dir = tmp_path / ".engineeringagent" / "progress"
    excluded_dir.mkdir(parents=True, exist_ok=True)
    (excluded_dir / "excluded.txt").write_text(
        f"{removed_reviewer_id}\n",
        encoding="utf-8",
    )
    _run_git(tmp_path, "add", ".engineeringagent/progress/excluded.txt")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["rule_id"] == "quality.purge-invariant"
    assert payload["status"] == "fail"
    violations = payload.get("violations")
    assert isinstance(violations, list)
    assert any("active.txt" in item and "purge invariant" in item for item in violations)
    assert all(".engineeringagent/progress/excluded.txt" not in item for item in violations)


def test_purge_invariant_rule_includes_legacy_progress_paths(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Legacy progress paths remain part of the tracked-file purge scan."""
    _run_git(tmp_path, "init")

    removed_reviewer_id = "_".join(["readme", "process"])
    legacy_artifact = tmp_path / "progress" / "runs" / "runs.jsonl"
    legacy_artifact.parent.mkdir(parents=True, exist_ok=True)
    legacy_artifact.write_text(
        f"artifact marker: {removed_reviewer_id}\n",
        encoding="utf-8",
    )
    _run_git(tmp_path, "add", "progress/runs/runs.jsonl")

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload.get("violations")
    assert isinstance(violations, list)
    assert any("progress/runs/runs.jsonl" in item for item in violations)


def test_purge_invariant_rule_reports_git_ls_files_failure(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """A broken git index surfaces as a failing fitness violation."""
    (tmp_path / ".git").mkdir(parents=True, exist_ok=True)

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 1
    assert payload["status"] == "fail"
    violations = payload.get("violations")
    assert isinstance(violations, list)
    assert any("git ls-files failed" in item for item in violations)
