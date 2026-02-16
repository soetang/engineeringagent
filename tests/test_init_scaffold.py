from __future__ import annotations

import yaml
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
from engineeringagent.init_scaffold import (
    build_baseline_scaffold_manifest,
    build_init_scaffold_manifest,
)


def _invoke_cli(args: list[str]):
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def test_build_baseline_scaffold_manifest_excludes_reviewers_by_default() -> None:
    manifest = build_baseline_scaffold_manifest()

    assert "harness/reviewers.yaml" not in manifest
    assert "harness/reviewers/prompts/code_simplifier.md" not in manifest
    assert "harness/reviewers/prompts/readme_process.md" not in manifest


def test_build_baseline_scaffold_manifest_ignores_include_reviewers_flag() -> None:
    manifest = build_baseline_scaffold_manifest(include_reviewers=True)

    assert "harness/reviewers.yaml" not in manifest
    assert "harness/reviewers/prompts/code_simplifier.md" not in manifest
    assert "harness/reviewers/prompts/readme_process.md" not in manifest


def test_init_rejects_include_reviewers_flag() -> None:
    result = _invoke_cli(["init", "--include-reviewers"])

    assert result.exit_code == 2
    assert "No such option" in result.stderr
    assert "--include-reviewers" in result.stderr


def test_init_slim_scaffold_has_no_rules_referencing_missing_scripts() -> None:
    manifest = build_init_scaffold_manifest(pack="slim")

    rules_text = manifest["harness/fitness-functions/rules.yaml"]
    payload = yaml.safe_load(rules_text)

    assert isinstance(payload, dict)
    assert payload.get("contract_version") == "1.0"

    rules = payload.get("rules")
    assert isinstance(rules, list)

    for rule in rules:
        if not isinstance(rule, dict):
            continue
        command = rule.get("command")
        if not isinstance(command, list):
            continue
        for token in command:
            if not isinstance(token, str):
                continue
            if token.startswith("harness/fitness-functions/") and token.endswith(".py"):
                assert token in manifest, (
                    f"slim scaffold rule references missing script: {token}"
                )
