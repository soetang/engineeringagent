from __future__ import annotations

from typer.testing import CliRunner

from engineeringagent import cli as cli_module
from engineeringagent.init_scaffold import build_baseline_scaffold_manifest


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
