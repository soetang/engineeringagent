from __future__ import annotations

from pathlib import Path
import sys

import pytest
import yaml

from engineeringagent.domain.quality import ChangedPathsResult
from engineeringagent.checks import run_checks
from tests.checks.run_checks_contract_support import write_checks_yaml


def test_run_checks_fitness_does_not_call_legacy_runtime(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_all:",
                "    type: fitness",
                "    scope: all",
                "",
            ]
        ),
    )

    # Avoid touching git in tmp_path.
    monkeypatch.setattr(
        "engineeringagent.checks.api.collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=None,
        ),
        raising=True,
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["fitness"],
    )
    assert result.ok
    assert "[check:fitness_all] type=fitness scope=all" in result.output


def test_run_checks_fitness_surfaces_statement_budget_offenders(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    remediation = (
        "Reduce duplicated control-flow before splitting; extract cohesive concerns "
        "into existing folders first, or into a clearly named domain subpackage "
        "when needed; avoid root-level helper sprawl; for tests, prefer "
        "fixtures/builders/parametrization over repeated setup/assertions."
    )
    write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  fitness_statement_budget:",
                "    type: fitness",
                "    rule_ids:",
                "      - architecture.module-statement-budget",
                "",
            ]
        ),
    )
    policy_dir = tmp_path / "harness" / "fitness_functions" / "policies"
    policy_dir.mkdir(parents=True, exist_ok=True)
    (policy_dir / "module_statement_budget_policy.yaml").write_text(
        yaml.safe_dump({"budgets": [{"root": "src/engineeringagent", "cap": 1}]}),
        encoding="utf-8",
    )
    (tmp_path / "src" / "engineeringagent").mkdir(parents=True, exist_ok=True)
    (tmp_path / "src" / "engineeringagent" / "over_budget.py").write_text(
        "value = 1\nother = 2\n",
        encoding="utf-8",
    )
    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
    manifest_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "rules": [
                    {
                        "rule_id": "architecture.module-statement-budget",
                        "name": "Module statement budget",
                        "summary": "Enforce AST-based non-doc statement caps for Python modules.",
                        "rationale": "Limits module sprawl using executable structure.",
                        "remediation": remediation,
                        "scope": "src/engineeringagent",
                        "severity": "error",
                        "side_effect_free": True,
                        "adapter": "command",
                        "config_file": "policies/module_statement_budget_policy.yaml",
                        "command": [
                            sys.executable,
                            str(
                                repo_root
                                / "harness"
                                / "fitness_functions"
                                / "rules"
                                / "check_module_statement_budget.py"
                            ),
                        ],
                    }
                ],
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    result = run_checks(tmp_path, phase="iteration_end", checks=["fitness"])

    assert not result.ok
    assert (
        "[fitness:architecture.module-statement-budget] status=fail"
        in result.output
    )
    assert "src/engineeringagent/over_budget.py: statements=2 cap=1" in result.output
    assert remediation not in result.output
