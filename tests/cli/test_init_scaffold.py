from __future__ import annotations

from importlib.resources import files
import inspect
import yaml
import pytest
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
import engineeringagent.init_scaffold as init_scaffold_module
from engineeringagent.init_scaffold import (
    build_baseline_scaffold_manifest,
    build_init_scaffold_manifest,
)


def _invoke_cli(args: list[str]):
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def test_build_baseline_scaffold_manifest_excludes_reviewers_by_default() -> None:
    manifest = build_baseline_scaffold_manifest()

    removed_prompt = (
        "harness/reviewers/prompts/" + "_".join(["readme", "process"]) + ".md"
    )

    assert "harness/reviewers.yaml" not in manifest
    assert "harness/gates.yaml" not in manifest
    assert "docs/spec/schemas/feature.schema.json" not in manifest
    assert "harness/reviewers/prompts/code_simplifier.md" not in manifest
    assert removed_prompt not in manifest


def test_build_baseline_scaffold_manifest_api_excludes_include_reviewers() -> None:
    parameters = inspect.signature(build_baseline_scaffold_manifest).parameters

    assert "include_reviewers" not in parameters


def test_build_init_scaffold_manifest_excludes_legacy_harness_files() -> None:
    slim_manifest = build_init_scaffold_manifest(pack="slim")
    assert "harness/gates.yaml" not in slim_manifest
    assert "harness/reviewers.yaml" not in slim_manifest

    standard_manifest = build_init_scaffold_manifest(pack="standard")
    assert "harness/gates.yaml" not in standard_manifest
    assert "harness/reviewers.yaml" not in standard_manifest


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


def test_render_scaffold_template_supports_substitutions_argument() -> None:
    rendered = init_scaffold_module._render_scaffold_template(  # pylint: disable=protected-access
        "AGENTS.md",
        substitutions={"unused": "value"},
    )
    assert isinstance(rendered, str)
    assert rendered


def test_build_baseline_scaffold_manifest_user_docs_are_deterministic() -> None:
    first = build_baseline_scaffold_manifest()
    second = build_baseline_scaffold_manifest()

    assert first == second

    first_policy = yaml.safe_load(first["harness/scaffold_policy.yaml"])
    second_policy = yaml.safe_load(second["harness/scaffold_policy.yaml"])
    assert first_policy == second_policy


def test_build_baseline_scaffold_manifest_user_docs_follow_template_categories() -> (
    None
):
    template_root = files("engineeringagent.scaffold_templates")
    category_roots = {"principle": "principles", "reference": "references"}
    expected_docs: set[str] = set()
    expected_exact_sync: set[tuple[str, str]] = set()

    for entry in template_root.iterdir():
        if not entry.is_file():
            continue
        template_name = entry.name
        if not template_name.endswith(".md"):
            continue
        category, _, relative_name = template_name.partition(".")
        docs_subdir = category_roots.get(category)
        if docs_subdir is None:
            continue
        docs_path = f"docs/{docs_subdir}/{relative_name}"
        expected_docs.add(docs_path)
        expected_exact_sync.add((docs_path, template_name))

    manifest = build_baseline_scaffold_manifest(docs_dir="docs", profile="core")
    policy = yaml.safe_load(manifest["harness/scaffold_policy.yaml"])

    assert expected_docs
    assert set(policy["user_docs"]) == expected_docs
    assert set(policy["scaffold_docs"]) == expected_docs
    assert {
        (entry["docs_path"], entry["template_name"]) for entry in policy["exact_sync"]
    } == expected_exact_sync
    assert all(docs_path in manifest for docs_path in expected_docs)
    assert "docs/architecture/Architecture.md" not in manifest
    assert "docs/architecture/Architecture.md" not in policy["user_docs"]
    assert "docs/architecture/Architecture.md" not in policy["scaffold_docs"]
    assert all(
        entry["docs_path"] != "docs/architecture/Architecture.md"
        for entry in policy["exact_sync"]
    )


def test_build_precommit_config_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="unsupported scaffold profile"):
        init_scaffold_module._build_precommit_config("unknown")  # pylint: disable=protected-access


def test_build_baseline_scaffold_manifest_rejects_unknown_profile() -> None:
    with pytest.raises(ValueError, match="unsupported scaffold profile"):
        build_baseline_scaffold_manifest(profile="unknown")


def test_build_init_scaffold_manifest_rejects_unknown_pack() -> None:
    with pytest.raises(ValueError, match="unsupported init pack"):
        build_init_scaffold_manifest(pack="unknown")


def test_init_surface_modules_avoid_backend_specific_literals() -> None:
    """Keep init/CLI modules free of backend-specific literal strings."""

    cli_source = inspect.getsource(cli_module).lower()
    scaffold_source = inspect.getsource(init_scaffold_module).lower()

    assert "opencode" not in cli_source
    assert "opencode" not in scaffold_source
