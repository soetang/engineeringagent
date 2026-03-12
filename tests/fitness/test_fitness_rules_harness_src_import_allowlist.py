from __future__ import annotations

# Tests load fitness scripts and call internal helpers.
# pylint: disable=protected-access

import importlib.util
from pathlib import Path


def _load_checker_module(repo_root: Path):
    checker_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "rules"
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
    """Scan manifest-declared harness scripts, not only check_* filenames."""
    checker = _load_checker_module(repo_root)

    harness_root = tmp_path / "harness" / "fitness_functions"
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
                "      - harness/fitness_functions/validate_custom.py",
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
        "harness/fitness_functions/validate_custom.py: imports disallowed module engineeringagent.cli.main (allowed: engineeringagent.domain.specification, engineeringagent.adapters.config, engineeringagent.adapters.quality.fitness)"
    ]


def test_checker_allows_domain_and_config_imports_for_harness_rules(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Allow harness rules to import spec and config helpers from owning modules."""
    checker = _load_checker_module(repo_root)

    harness_root = tmp_path / "harness" / "fitness_functions"
    harness_root.mkdir(parents=True)
    (harness_root / "rules.yaml").write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: architecture.tmp",
                "    command:",
                "      - uv",
                "      - run",
                "      - python",
                "      - harness/fitness_functions/validate_custom.py",
                "",
            ]
        ),
        encoding="utf-8",
    )
    (harness_root / "validate_custom.py").write_text(
        "\n".join(
            [
                "from engineeringagent.adapters.config import resolve_specifications_root",
                "from engineeringagent.domain.specification import (",
                "    iter_feature_files,",
                ")",
                "",
                "def run() -> None:",
                "    _ = iter_feature_files",
                "    _ = resolve_specifications_root",
                "",
            ]
        ),
        encoding="utf-8",
    )

    assert checker._collect_violations(tmp_path) == []
