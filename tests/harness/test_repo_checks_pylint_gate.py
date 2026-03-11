from __future__ import annotations

from pathlib import Path

import yaml


def test_repo_checks_yaml_includes_pylint_gate_contract(repo_root: Path) -> None:
    checks_path = repo_root / "harness" / "checks.yaml"
    document = yaml.safe_load(checks_path.read_text(encoding="utf-8"))
    assert isinstance(document, dict)

    defaults = document.get("defaults", {})
    assert isinstance(defaults, dict)
    defaults_when = defaults.get("when", {})
    assert isinstance(defaults_when, dict)
    assert defaults_when.get("phase") == "iteration_end"

    checks = document.get("checks", {})
    assert isinstance(checks, dict)
    groups = document.get("groups", [])
    assert isinstance(groups, list)
    assert {
        "group_id": "lint",
        "description": "Additional lint coverage that complements Ruff.",
        "checks": ["pylint_validate"],
    } in groups

    pylint_validate = checks.get("pylint_validate")
    assert isinstance(pylint_validate, dict)

    assert pylint_validate.get("type") == "command"
    assert (
        pylint_validate.get("command")
        == "uv run pylint --score=n --reports=n src/engineeringagent tests harness"
    )

    when = pylint_validate.get("when", {})
    assert isinstance(when, dict)
    assert when.get("on_change") == ["src/**/*.py", "tests/**/*.py", "harness/**/*.py"]
