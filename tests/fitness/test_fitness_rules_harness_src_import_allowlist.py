from __future__ import annotations

# Tests load fitness scripts and call internal helpers.
# pylint: disable=protected-access

import importlib.util
from pathlib import Path


def _load_checker_module(repo_root: Path):
    checker_path = (
        repo_root
        / "harness"
        / "fitness-functions"
        / "check_harness_src_import_allowlist.py"
    )
    spec = importlib.util.spec_from_file_location(
        "engineeringagent_tests.harness_src_import_allowlist_checker",
        checker_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_checker_scans_rules_manifest_scripts_not_just_check_prefix(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    checker = _load_checker_module(repo_root)

    harness_root = tmp_path / "harness" / "fitness-functions"
    harness_root.mkdir(parents=True)
    (harness_root / "rules.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: architecture.tmp",  # minimal manifest entry
                "    command:",
                "      - uv",
                "      - run",
                "      - python",
                "      - harness/fitness-functions/validate_custom.py",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (harness_root / "validate_custom.py").write_text(
        "\n".join(
            [
                "from engineeringagent.cli import main",  # disallowed
                "\n",
                "def run() -> None:",
                "    _ = main",
                "",
            ]
        ),
        encoding="utf-8",
    )

    violations = checker._collect_violations(tmp_path)
    assert violations == [
        "harness/fitness-functions/validate_custom.py: imports disallowed module engineeringagent.cli.main (allowed: engineeringagent.checks)"
    ]
