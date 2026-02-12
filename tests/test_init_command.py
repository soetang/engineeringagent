from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest
import yaml

from engineeringagent.cli import build_parser, cmd_init
from engineeringagent.init_scaffold import build_scaffold_agents_markdown


def test_init_subcommand_registered() -> None:
    """Verify the init command is registered on the root parser."""
    parser = build_parser()

    args = parser.parse_args(["init"])

    assert args.command == "init"
    assert args.func is cmd_init


def test_init_prompts_when_docs_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: Any,
) -> None:
    """Verify init prompts for docs conflict and supports reuse mode."""
    (tmp_path / "docs").mkdir(parents=True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "reuse")

    parser = build_parser()
    args = parser.parse_args(["--project-root", str(tmp_path), "init"])

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "docs_dir=docs" in output
    assert (tmp_path / "docs" / "spec" / "features" / ".gitkeep").exists()


def test_init_can_use_separate_docs_directory(tmp_path: Path, capsys: Any) -> None:
    """Verify init can scaffold into a distinct docs directory."""
    (tmp_path / "docs").mkdir(parents=True)

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--docs-mode",
            "separate",
            "--scaffold-docs-dir",
            "docs.engineeringagent",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "docs_dir=docs.engineeringagent" in output
    assert not (tmp_path / "docs" / "spec").exists()
    assert (
        tmp_path / "docs.engineeringagent" / "spec" / "features" / ".gitkeep"
    ).exists()


def test_init_agents_conflict_overwrite(tmp_path: Path, capsys: Any) -> None:
    """Verify init can explicitly overwrite an existing AGENTS.md."""
    (tmp_path / "AGENTS.md").write_text("user guidance\n", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--agents-mode",
            "overwrite",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "agents_mode=overwrite" in output
    scaffold_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "user guidance" not in scaffold_agents
    assert "engineeringagent validate" in scaffold_agents


def test_init_agents_conflict_preserve_and_create_merge_spec(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify preserve mode renames AGENTS and creates a merge follow-up spec."""
    (tmp_path / "AGENTS.md").write_text("legacy guidance\n", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--agents-mode",
            "preserve",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "agents_mode=preserve" in output
    assert "agents_backup=AGENTS.user.md" in output

    assert (tmp_path / "AGENTS.user.md").read_text(
        encoding="utf-8"
    ) == "legacy guidance\n"
    scaffold_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "legacy guidance" not in scaffold_agents

    merge_spec_path = (
        tmp_path
        / "docs"
        / "spec"
        / "features"
        / "FEAT-900-merge-preserved-agents-guidance.yaml"
    )
    assert merge_spec_path.exists()
    assert "AGENTS.user.md" in merge_spec_path.read_text(encoding="utf-8")


def test_init_agents_conflict_abort(tmp_path: Path, capsys: Any) -> None:
    """Verify abort mode keeps AGENTS and exits without scaffold writes."""
    (tmp_path / "AGENTS.md").write_text("do not touch\n", encoding="utf-8")

    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--agents-mode",
            "abort",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "init aborted" in output
    assert (tmp_path / "AGENTS.md").read_text(encoding="utf-8") == "do not touch\n"
    assert not (tmp_path / "docs" / "spec").exists()


def test_generated_agents_includes_validate_commands() -> None:
    """Verify scaffolded AGENTS guidance includes setup validation commands."""
    scaffold_agents = build_scaffold_agents_markdown()

    assert "engineeringagent validate" in scaffold_agents
    assert "engineeringagent gates list" in scaffold_agents
    assert "engineeringagent gates run --profile precommit" in scaffold_agents


def test_generated_agents_excludes_run_command_guidance() -> None:
    """Verify scaffolded AGENTS guidance excludes run-loop command guidance."""
    scaffold_agents = build_scaffold_agents_markdown()

    assert "engineeringagent run" not in scaffold_agents


def test_init_writes_precommit_and_empty_gate_profiles(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify init writes pre-commit wiring and empty gate profile stubs."""
    parser = build_parser()
    args = parser.parse_args(["--project-root", str(tmp_path), "init"])

    code = args.func(args)
    _ = capsys.readouterr()

    assert code == 0

    precommit_config = (tmp_path / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert "engineeringagent gates run --profile precommit" in precommit_config

    gates_config = yaml.safe_load(
        (tmp_path / "harness" / "gates.yaml").read_text(encoding="utf-8")
    )
    assert gates_config["profiles"]["precommit"] == []
    assert gates_config["profiles"]["loop_fast"] == []
    assert gates_config["gates"] == {}
