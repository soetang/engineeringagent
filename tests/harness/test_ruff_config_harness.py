from __future__ import annotations

from pathlib import Path

import tomli


def test_ruff_per_file_ignores_exempt_harness_fitness_functions(
    repo_root: Path,
) -> None:
    pyproject_text = (repo_root / "pyproject.toml").read_text(encoding="utf-8")
    config = tomli.loads(pyproject_text)

    per_file_ignores = config["tool"]["ruff"]["lint"].get("per-file-ignores", {})

    lint_select = set(config["tool"]["ruff"]["lint"].get("select", []))
    lint_extend_select = set(config["tool"]["ruff"]["lint"].get("extend-select", []))
    enabled_rules = lint_select | lint_extend_select

    expected_path = "harness/fitness-functions/*.py"
    assert expected_path in per_file_ignores

    ignored_rules = set(per_file_ignores[expected_path])
    expected_ignored_rules = {
        "D103",
        "D417",
        "C901",
        "PLR0912",
        "PLR0913",
        "PLR0915",
    }

    # These rules should be enabled globally so that per-file ignores are meaningful.
    assert expected_ignored_rules.issubset(enabled_rules)

    # But harness fitness-function scripts are allowed to violate them.
    assert expected_ignored_rules.issubset(ignored_rules)
