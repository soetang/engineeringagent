from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest
from typer.testing import CliRunner

from engineeringagent.presentation import cli as cli_module
from tests.presentation.cli.init_command_support import (
    UV_RUN_TOKEN,
    UVX_TOKEN,
    invoke_cli,
    patch_non_tty,
    patch_tty,
    tomllib,
)
from tests.helpers.fitness_manifest import write_shell_contract_manifest


def test_checks_catalog_accepts_absolute_manifest_and_output_paths(
    tmp_path: Path,
) -> None:
    manifest_path = write_shell_contract_manifest(tmp_path)
    output_path = tmp_path / "catalog.md"
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(
        cli_module.build_typer_app(),
        [
            "--project-root",
            str(tmp_path),
            "checks",
            "catalog",
            "--manifest-path",
            str(manifest_path),
            "--format",
            "markdown",
            "--output",
            str(output_path),
        ],
    )

    assert result.exit_code == 0
    assert "checks catalog written:" in result.stdout
    assert output_path.exists()


def test_init_rejects_empty_scaffold_docs_dir(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_non_tty(monkeypatch)

    result = invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--backend",
            "opencode",
            "--agents-launcher",
            "uvx",
            "--scaffold-docs-dir",
            "",
            "--no-precommit-install",
        ]
    )

    assert result.exit_code == 1
    assert "init input error: --scaffold-docs-dir cannot be empty" in result.stdout


def test_cmd_init_rejects_invalid_docs_mode_when_docs_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    patch_non_tty(monkeypatch)
    (tmp_path / "docs").mkdir()

    result = cli_module.cmd_init(
        SimpleNamespace(
            project_root=str(tmp_path),
            force=False,
            scaffold_profile="core",
            docs_mode="invalid",
            scaffold_docs_dir="docs.engineeringagent",
            agents_mode=None,
            pack="slim",
            backend="opencode",
            agents_launcher="uvx",
            model="gpt-5",
            no_precommit_install=True,
        )
    )

    assert result == 1
    assert (
        "init input error: docs mode must be 'reuse' or 'separate' when docs/ exists"
        in capsys.readouterr().out
    )


def test_init_rejects_invalid_agents_prompt_selection(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_non_tty(monkeypatch)
    (tmp_path / "AGENTS.md").write_text("# AGENTS\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "invalid")

    result = invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--backend",
            "opencode",
            "--no-precommit-install",
        ]
    )

    assert result.exit_code == 1
    assert (
        "init input error: AGENTS mode must be 'overwrite', 'preserve', or 'abort' "
        "when AGENTS.md exists"
    ) in result.stdout


def test_init_preserve_mode_reports_skipped_merge_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_non_tty(monkeypatch)
    (tmp_path / "AGENTS.md").write_text("# User agents\n", encoding="utf-8")
    (tmp_path / "AGENTS.user.md").write_text("# Existing backup\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "preserve")
    merge_spec_path = (
        tmp_path
        / "docs"
        / "specifications"
        / "features"
        / "FEAT-900-merge-preserved-agents-guidance.yaml"
    )
    merge_spec_path.parent.mkdir(parents=True, exist_ok=True)
    merge_spec_path.write_text("id: FEAT-900\n", encoding="utf-8")

    result = invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--backend",
            "opencode",
            "--docs-mode",
            "reuse",
            "--agents-launcher",
            "uvx",
            "--no-precommit-install",
        ]
    )

    assert result.exit_code == 0
    assert (
        "merge_spec_skipped=docs/specifications/features/FEAT-900-merge-preserved-agents-guidance.yaml"
        in result.stdout
    )
    backup_paths = sorted(tmp_path.glob("AGENTS.user*.md"))
    assert len(backup_paths) == 2
    assert "agents_backup=" in result.stdout


def test_version_flag_prints_version_and_exits_zero(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(cli_module.importlib_metadata, "version", lambda _name: "1.2.3")
    runner = CliRunner(mix_stderr=False)

    result = runner.invoke(cli_module.build_typer_app(), ["--version"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "1.2.3"


def test_cmd_init_uses_cli_resolvers_for_backend_and_launcher_prompts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    patch_tty(monkeypatch, backends=("mock-b", "opencode"), default_backend="mock-b")
    answers = iter(("opencode", "uv-run"))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    result = cli_module.cmd_init(
        SimpleNamespace(
            project_root=str(tmp_path),
            force=False,
            scaffold_profile="core",
            scaffold_docs_dir="docs",
            pack="slim",
            backend=None,
            docs_mode=None,
            agents_mode=None,
            agents_launcher=None,
            model="gpt-5",
            no_precommit_install=True,
        )
    )

    assert result == 0
    assert tomllib.loads(
        (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    ) == {"agents": {"backend": "opencode"}}

    rendered_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert UV_RUN_TOKEN in rendered_agents
    assert UVX_TOKEN not in rendered_agents
