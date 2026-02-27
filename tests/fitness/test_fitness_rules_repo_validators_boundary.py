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
        / "fitness-functions"
        / "check_repo_validators_boundary.py"
    )


def _write_module(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


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


def test_repo_validators_boundary_fitness_rule_registered() -> None:
    """Manifest declares the repo validators boundary rule exactly once."""
    manifest_path = Path("harness/fitness-functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)

    rules = manifest.get("rules")
    assert isinstance(rules, list)

    matching = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.repo-validators-boundary"
    ]
    assert len(matching) == 1

    command = matching[0].get("command")
    assert isinstance(command, list)
    assert "harness/fitness-functions/check_repo_validators_boundary.py" in command
    assert Path("harness/fitness-functions/check_repo_validators_boundary.py").exists()


def test_repo_validators_boundary_fitness_rule_passes_clean_repo() -> None:
    """Checker passes against the current repository layout."""
    proc = subprocess.run(
        [
            sys.executable,
            "harness/fitness-functions/check_repo_validators_boundary.py",
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0

    payload = json.loads(proc.stdout)
    assert payload["rule_id"] == "architecture.repo-validators-boundary"
    assert payload["status"] == "pass"


def test_repo_validators_boundary_reports_missing_import_and_legacy_definition(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Checker fails when orchestrator regresses to legacy policy ownership."""
    _write_module(
        tmp_path,
        "src/engineeringagent/checks/validate/repo_policy_feature_ids.py",
        "def append_feature_id_invariant_issues(messages, *, ctx):\n    return None\n",
    )
    _write_module(
        tmp_path,
        "src/engineeringagent/checks/validate/repo_policy_docs_map.py",
        "def append_agents_docs_map_issues(messages, *, project_root, docs_root):\n    return None\n",
    )
    _write_module(
        tmp_path,
        "src/engineeringagent/checks/validate/repo_policy_purge_invariant.py",
        "def append_purge_invariant_issues(messages, *, project_root):\n    return None\n",
    )
    _write_module(
        tmp_path,
        "src/engineeringagent/checks/validate/repo_validators.py",
        "\n".join(
            [
                "from engineeringagent.checks.validate.repo_policy_feature_ids import append_feature_id_invariant_issues",
                "from engineeringagent.checks.validate.repo_policy_purge_invariant import append_purge_invariant_issues",
                "",
                "def _purge_forbidden_needles() -> list[str]:",
                "    return []",
            ]
        )
        + "\n",
    )

    proc, payload = _run_checker(tmp_path, checker_path=_script_path(repo_root))

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.repo-validators-boundary"
    assert payload["status"] == "fail"

    violations = payload.get("violations")
    assert isinstance(violations, list)
    assert len(violations) == 2
    assert any(
        "missing import 'append_agents_docs_map_issues'" in violation
        for violation in violations
    )
    assert any(
        "owns extracted policy definition '_purge_forbidden_needles'" in violation
        for violation in violations
    )
