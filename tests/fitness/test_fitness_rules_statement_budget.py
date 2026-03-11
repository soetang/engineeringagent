from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from typing import cast

import yaml


def _script_path(repo_root: Path) -> Path:
    return (
        repo_root
        / "harness"
        / "fitness_functions"
        / "check_module_statement_budget.py"
    )


def _write_file(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_policy(project_root: Path, budgets: list[dict[str, object]]) -> Path:
    policy_path = project_root / "module-statement-budget-policy.yaml"
    policy_path.write_text(
        yaml.safe_dump({"budgets": budgets}, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return policy_path


def _copy_file(project_root: Path, source_root: Path, relative_path: str) -> None:
    source_path = source_root / relative_path
    destination_path = project_root / relative_path
    destination_path.parent.mkdir(parents=True, exist_ok=True)
    destination_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")


def _statement_module(statement_count: int) -> str:
    return "\n".join(f"value_{index} = {index}" for index in range(statement_count))


def _run_checker(
    project_root: Path,
    *,
    checker_path: Path,
    config_file: Path | None = None,
) -> tuple[subprocess.CompletedProcess[str], dict[str, object]]:
    command = [sys.executable, str(checker_path)]
    if config_file is not None:
        command.extend(["--config-file", str(config_file)])

    proc = subprocess.run(
        command,
        cwd=project_root,
        capture_output=True,
        text=True,
        check=False,
    )
    payload = json.loads(proc.stdout)
    return proc, payload


def _summary(payload: dict[str, object]) -> str:
    return cast(str, payload["summary"])


def test_statement_budget_rule_counts_non_doc_ast_statements(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/budgeted.py",
        "\n".join(
            [
                '"""Module docstring."""',
                "",
                "# Comments must not affect the budget.",
                "value = 1",
                "",
                "def build_value() -> int:",
                '    """Function docstring."""',
                "    interim = value + 1",
                "    return interim",
                "",
                "class Budgeted:",
                '    """Class docstring."""',
                "    label = 'budgeted'",
            ]
        ),
    )
    policy_file = _write_policy(
        tmp_path,
        [{"root": "src/engineeringagent", "cap": 5}],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_file,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.module-statement-budget"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "src/engineeringagent/budgeted.py: statements=6 cap=5"
    ]


def test_statement_budget_rule_counts_non_doc_bare_string_expressions(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/budgeted.py",
        "\n".join(
            [
                '"""Module docstring."""',
                "",
                "value = 1",
                '"module noop string"',
                "",
                "def build_value() -> int:",
                '    """Function docstring."""',
                "    interim = value + 1",
                '    \"function noop string\"',
                "    return interim",
                "",
                "class Budgeted:",
                '    """Class docstring."""',
                "    label = 'budgeted'",
                '    \"class noop string\"',
            ]
        ),
    )
    policy_file = _write_policy(
        tmp_path,
        [{"root": "src/engineeringagent", "cap": 8}],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_file,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.module-statement-budget"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "src/engineeringagent/budgeted.py: statements=9 cap=8"
    ]


def test_statement_budget_rule_enforces_budget_per_configured_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/ok.py",
        "\n".join(
            [
                "def ok() -> int:",
                "    return 1",
            ]
        ),
    )
    _write_file(
        tmp_path,
        "tests/test_over_budget.py",
        "\n".join(
            [
                "def test_budget() -> None:",
                "    assert True",
            ]
        ),
    )
    _write_file(
        tmp_path,
        "harness/helper.py",
        "\n".join(
            [
                "def helper() -> None:",
                "    return None",
            ]
        ),
    )
    policy_file = _write_policy(
        tmp_path,
        [
            {"root": "src/engineeringagent", "cap": 2},
            {"root": "tests", "cap": 1},
            {"root": "harness", "cap": 2},
        ],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=policy_file,
    )

    assert proc.returncode == 0
    assert payload["status"] == "fail"
    assert payload["violations"] == ["tests/test_over_budget.py: statements=2 cap=1"]


def test_statement_budget_rule_uses_bundled_default_policy_thresholds(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    _write_file(
        tmp_path,
        "src/engineeringagent/over_budget.py",
        _statement_module(301),
    )
    _write_file(
        tmp_path,
        "harness/over_budget.py",
        _statement_module(301),
    )
    _write_file(
        tmp_path,
        "tests/test_over_budget.py",
        _statement_module(401),
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.module-statement-budget"
    assert payload["status"] == "fail"
    assert payload["violations"] == [
        "harness/over_budget.py: statements=301 cap=300",
        "src/engineeringagent/over_budget.py: statements=301 cap=300",
    ]


def test_phase_runtime_fixture_keeps_fe_181_modules_within_budget(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    for relative_path in (
        "src/engineeringagent/loop_runtime/feature_state.py",
        "tests/loop/test_loop_feature_iteration_verification.py",
    ):
        _copy_file(tmp_path, repo_root, relative_path)

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
    )

    assert proc.returncode == 0
    assert payload["status"] == "pass"
    assert payload["violations"] == []


def test_statement_budget_rule_errors_when_policy_is_invalid(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    invalid_policy = tmp_path / "invalid-policy.yaml"
    invalid_policy.write_text("budgets: not-a-list\n", encoding="utf-8")

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=invalid_policy,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.module-statement-budget"
    assert payload["status"] == "error"
    assert payload["violations"] == []
    assert _summary(payload).startswith("Native statement-budget scan failed:")


def test_statement_budget_rule_errors_when_policy_repeats_budget_root(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    duplicate_policy = _write_policy(
        tmp_path,
        [
            {"root": "src/engineeringagent", "cap": 300},
            {"root": "src/engineeringagent", "cap": 250},
        ],
    )

    proc, payload = _run_checker(
        tmp_path,
        checker_path=_script_path(repo_root),
        config_file=duplicate_policy,
    )

    assert proc.returncode == 0
    assert payload["rule_id"] == "architecture.module-statement-budget"
    assert payload["status"] == "error"
    assert payload["violations"] == []
    assert (
        _summary(payload)
        == "Native statement-budget scan failed: duplicate policy budget root: "
        "src/engineeringagent"
    )
