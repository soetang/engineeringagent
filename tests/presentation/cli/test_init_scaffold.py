from __future__ import annotations

import inspect
import yaml
import pytest
from typer.testing import CliRunner

from engineeringagent.presentation import cli as cli_module
import engineeringagent.bootstrap.init_scaffold as init_scaffold_module
from engineeringagent.bootstrap.init_scaffold import (
    AGENTS_LAUNCHER_CHOICES,
    AGENTS_LAUNCHER_COMMANDS,
    DEFAULT_AGENTS_LAUNCHER,
    build_baseline_scaffold_manifest,
    build_init_scaffold_manifest,
    build_scaffold_agents_markdown,
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
    assert "docs/specifications/schemas/feature.schema.json" not in manifest
    assert "harness/reviewers/prompts/code_simplifier.md" not in manifest
    assert removed_prompt not in manifest


def test_build_baseline_scaffold_manifest_api_excludes_include_reviewers() -> None:
    parameters = inspect.signature(build_baseline_scaffold_manifest).parameters

    assert "include_reviewers" not in parameters


def test_build_baseline_scaffold_manifest_excludes_user_guidance_templates() -> None:
    manifest = build_baseline_scaffold_manifest()

    assert not any(path.startswith("docs/references/") for path in manifest)
    assert not any(path.startswith("docs/principles/") for path in manifest)
    assert "docs/specifications/potential_features.yaml" not in manifest
    assert "docs/specifications/features/potential_features.yaml" not in manifest


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

    rules_text = manifest["harness/fitness_functions/rules.yaml"]
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
            if token.startswith("harness/fitness_functions/") and token.endswith(".py"):
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


def test_build_scaffold_agents_markdown_defaults_to_explicit_uvx() -> None:
    implicit_default = build_scaffold_agents_markdown()
    explicit_default = build_scaffold_agents_markdown(DEFAULT_AGENTS_LAUNCHER)

    assert implicit_default == explicit_default


def test_build_scaffold_agents_markdown_launcher_variants_are_deterministic() -> None:
    for launcher in AGENTS_LAUNCHER_CHOICES:
        rendered = build_scaffold_agents_markdown(launcher)
        assert isinstance(rendered, str)
        assert rendered
        selected_command = AGENTS_LAUNCHER_COMMANDS[launcher]
        assert f"`{selected_command}`" in rendered
        if launcher != DEFAULT_AGENTS_LAUNCHER:
            default_command = AGENTS_LAUNCHER_COMMANDS[DEFAULT_AGENTS_LAUNCHER]
            assert f"`{default_command}`" not in rendered


def test_build_scaffold_agents_markdown_rejects_unknown_launcher() -> None:
    with pytest.raises(ValueError, match="unsupported AGENTS launcher"):
        build_scaffold_agents_markdown("unknown")


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
