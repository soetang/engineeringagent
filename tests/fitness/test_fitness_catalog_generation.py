from __future__ import annotations

import json
from pathlib import Path
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
from engineeringagent.checks import render_fitness_catalog
from engineeringagent.checks.fitness.catalog import format_config_file
from tests.helpers.fitness_manifest import write_shell_contract_manifest


def test_fitness_catalog_markdown_generation(tmp_path: Path) -> None:
    write_shell_contract_manifest(tmp_path)

    output_path = tmp_path / "docs" / "fitness-functions" / "rules.md"
    runner = CliRunner(mix_stderr=False)
    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "catalog",
            "--format",
            "markdown",
            "--output",
            str(output_path.relative_to(tmp_path)),
        ],
    )

    assert result.exit_code == 0
    assert "checks catalog written:" in result.stdout
    assert output_path.exists()
    assert output_path.read_text(encoding="utf-8").strip() != ""


def test_fitness_catalog_json_generation(tmp_path: Path) -> None:
    manifest_path = write_shell_contract_manifest(tmp_path)

    payload = json.loads(
        render_fitness_catalog(
            tmp_path,
            manifest_path=manifest_path.relative_to(tmp_path),
            format="json",
        )
    )

    assert payload == [
        {
            "adapter": "command",
            "config_file": "harness/fitness-functions/policies/custom_shell_contract.yaml",
            "name": "Custom shell contract",
            "rationale": "Keeps custom adapters interoperable.",
            "remediation": "Update custom command output to the contract.",
            "rule_id": "custom.shell-contract",
            "scope": "harness/fitness-functions",
            "severity": "warning",
            "side_effect_free": True,
            "source": "custom",
            "summary": "Verify custom command envelope format.",
        }
    ]


def test_fitness_catalog_json_contract_is_sorted_and_complete(tmp_path: Path) -> None:
    manifest_path = tmp_path / "harness" / "fitness-functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        "\n".join(
            [
                'contract_version: "1.0"',
                "rules:",
                "  - rule_id: custom.z-last",
                "    name: Custom z-last",
                "    summary: Custom command rule z-last.",
                "    rationale: Exercise contract fields.",
                "    remediation: Update custom rules manifest.",
                "    scope: docs",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                "      - print('{}')",
                "  - rule_id: custom.a-first",
                "    name: Custom a-first",
                "    summary: Custom command rule a-first.",
                "    rationale: Exercise contract fields.",
                "    remediation: Update custom rules manifest.",
                "    scope: docs",
                "    severity: warning",
                "    side_effect_free: true",
                "    adapter: command",
                "    command:",
                "      - python",
                "      - -c",
                "      - print('{}')",
            ]
        ),
        encoding="utf-8",
    )

    payload = json.loads(
        render_fitness_catalog(
            tmp_path,
            manifest_path=manifest_path.relative_to(tmp_path),
            format="json",
        )
    )

    assert isinstance(payload, list)
    assert payload

    rule_ids = [entry["rule_id"] for entry in payload]
    assert rule_ids == sorted(rule_ids)

    required_keys = {
        "adapter",
        "config_file",
        "name",
        "rationale",
        "remediation",
        "rule_id",
        "scope",
        "severity",
        "side_effect_free",
        "source",
        "summary",
    }
    for entry in payload:
        assert set(entry.keys()) == required_keys


def test_format_config_file_returns_project_relative_path(tmp_path: Path) -> None:
    config_path = (
        tmp_path
        / "harness"
        / "fitness-functions"
        / "policies"
        / "custom_shell_contract.yaml"
    )
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text("rule_id: custom.shell-contract\n", encoding="utf-8")

    assert (
        format_config_file(config_path, project_root=tmp_path)
        == "harness/fitness-functions/policies/custom_shell_contract.yaml"
    )


def test_repo_fitness_catalog_excludes_retired_rigid_rules(repo_root: Path) -> None:
    payload = json.loads(render_fitness_catalog(repo_root, format="json"))
    rule_ids = {entry["rule_id"] for entry in payload}

    assert "architecture.feedback-no-truncation" not in rule_ids
    assert "architecture.fitness-catalog-docs-sync" not in rule_ids


def test_repo_fitness_catalog_includes_statement_budget_rule(repo_root: Path) -> None:
    payload = json.loads(render_fitness_catalog(repo_root, format="json"))
    statement_budget_rule = next(
        entry
        for entry in payload
        if entry["rule_id"] == "architecture.module-statement-budget"
    )

    assert statement_budget_rule["config_file"] == (
        "harness/fitness-functions/policies/module_statement_budget_policy.yaml"
    )
    remediation = statement_budget_rule["remediation"]

    assert remediation
    assert "Reduce duplicated control-flow before splitting" in remediation
    assert "existing folders first" in remediation
    assert "clearly named domain subpackage" in remediation
    assert "avoid root-level helper sprawl" in remediation
    assert "fixtures/builders/parametrization" in remediation


def test_repo_fitness_catalog_docs_surface_directionality_policy_config(
    repo_root: Path,
) -> None:
    payload = json.loads(render_fitness_catalog(repo_root, format="json"))
    directionality_rule = next(
        entry for entry in payload if entry["rule_id"] == "architecture.dep-directionality"
    )

    assert directionality_rule["config_file"] == (
        "harness/fitness-functions/policies/dependency_directionality.yaml"
    )

    checked_in_catalog = (repo_root / "docs" / "fitness-functions" / "rules.md").read_text(
        encoding="utf-8"
    )

    assert "architecture.dep-directionality" in checked_in_catalog
    assert (
        "harness/fitness-functions/policies/dependency_directionality.yaml"
        in checked_in_catalog
    )


def test_repo_fitness_catalog_source_first_scope_mentions_bundled_plan_surfaces(
    repo_root: Path,
) -> None:
    payload = json.loads(render_fitness_catalog(repo_root, format="json"))
    source_first_rule = next(
        entry
        for entry in payload
        if entry["rule_id"] == "architecture.source-first-loop-command-policy"
    )

    assert source_first_rule["scope"] == (
        "legacy spec verification, bundled plan.md phases/examples, "
        "packaged plan-session/research-session guidance, "
        "contributor approach docs, "
        "loop implementation prompt template, "
        "docs/fixtures/real_opencode_hello_world_plan_template.md, and "
        "harness/checks.yaml"
    )

    checked_in_catalog = (repo_root / "docs" / "fitness-functions" / "rules.md").read_text(
        encoding="utf-8"
    )

    assert "bundled plan.md phases/examples" in checked_in_catalog
    assert "packaged plan-session/research-session guidance" in checked_in_catalog
    assert "contributor approach docs" in checked_in_catalog
    assert "loop implementation prompt template" in checked_in_catalog
