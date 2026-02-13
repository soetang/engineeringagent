from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
import yaml

from engineeringagent.cli import build_parser, cmd_init
from engineeringagent.init_scaffold import (
    build_baseline_scaffold_manifest,
    build_scaffold_agents_markdown,
)


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


def test_generated_agents_is_reference_first_and_minimal() -> None:
    """Verify scaffolded AGENTS guidance is concise and reference-oriented."""
    scaffold_agents = build_scaffold_agents_markdown()

    assert "Keep this file concise" in scaffold_agents
    assert "## System of Record (Read in this order)" in scaffold_agents
    assert "## Repo Extensions (Fill In)" in scaffold_agents
    assert "engineeringagent validate" in scaffold_agents
    assert "engineeringagent gates list" in scaffold_agents
    assert "engineeringagent gates run --profile precommit" in scaffold_agents


def test_generated_agents_keeps_major_principles() -> None:
    """Verify scaffolded AGENTS guidance preserves major operating principles."""
    scaffold_agents = build_scaffold_agents_markdown()

    assert "Humans steer, agents execute." in scaffold_agents
    assert "One feature focus per cycle." in scaffold_agents
    assert (
        "Keep audience split explicit: `README.md` for human onboarding"
        in scaffold_agents
    )


def test_init_writes_precommit_and_empty_gate_profiles(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify init writes pre-commit wiring, gate stubs, and fitness declarations."""
    parser = build_parser()
    args = parser.parse_args(["--project-root", str(tmp_path), "init"])

    code = args.func(args)
    _ = capsys.readouterr()

    assert code == 0

    precommit_config = (tmp_path / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert "entry: engineeringagent gates run --profile precommit" in precommit_config
    assert "uvx --from . engineeringagent" not in precommit_config
    assert "engineeringagent-commit-msg" not in precommit_config

    gates_config = yaml.safe_load(
        (tmp_path / "harness" / "gates.yaml").read_text(encoding="utf-8")
    )
    assert gates_config["profiles"]["precommit"] == []
    assert gates_config["profiles"]["loop_fast"] == []
    assert gates_config["gates"] == {}

    fitness_manifest = yaml.safe_load(
        (tmp_path / "harness" / "fitness-functions" / "rules.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert fitness_manifest == {
        "contract_version": "1.0",
        "rules": [
            {"builtin": "architecture.dep-directionality"},
            {"builtin": "architecture.loop-subprocess-boundary"},
            {"builtin": "architecture.scaffold-template-locality"},
        ],
    }


def test_init_defaults_to_core_language_agnostic_profile(
    tmp_path: Path,
    capsys: Any,
) -> None:
    """Verify init defaults to the language-agnostic core scaffold profile."""
    parser = build_parser()
    args = parser.parse_args(["--project-root", str(tmp_path), "init"])

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "profile=core" in output

    precommit_config = (tmp_path / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert "entry: engineeringagent gates run --profile precommit" in precommit_config
    assert "uvx --from ." not in precommit_config
    assert "engineeringagent-commit-msg" not in precommit_config


def test_init_python_uv_profile_available(tmp_path: Path, capsys: Any) -> None:
    """Verify init supports the optional python_uv scaffold profile."""
    parser = build_parser()
    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--scaffold-profile",
            "python_uv",
        ]
    )

    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert "profile=python_uv" in output

    precommit_config = (tmp_path / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert (
        "entry: uvx --from . engineeringagent gates run --profile precommit"
        in precommit_config
    )
    assert "engineeringagent-commit-msg" in precommit_config
    assert "validate_commit_messages.py --commit-msg-file" in precommit_config


def test_init_renders_scaffold_from_template_files() -> None:
    """Verify scaffold content is rendered from file-based template assets."""
    template_dir = files("engineeringagent.scaffold_templates")
    manifest = build_baseline_scaffold_manifest(profile="core")

    assert manifest[".pre-commit-config.yaml"] == template_dir.joinpath(
        "precommit.core.yaml"
    ).read_text(encoding="utf-8")
    assert manifest["AGENTS.md"] == template_dir.joinpath("AGENTS.md").read_text(
        encoding="utf-8"
    )


def test_init_template_rendering_is_deterministic() -> None:
    """Verify scaffold template rendering is deterministic across repeated calls."""
    first = build_baseline_scaffold_manifest(
        docs_dir="docs.engineeringagent",
        profile="python_uv",
    )
    second = build_baseline_scaffold_manifest(
        docs_dir="docs.engineeringagent",
        profile="python_uv",
    )

    assert first == second


def test_init_scaffolds_tool_generic_docs_only(tmp_path: Path, capsys: Any) -> None:
    """Verify init scaffolds reusable tool docs without repo-internal docs."""
    parser = build_parser()
    args = parser.parse_args(["--project-root", str(tmp_path), "init"])

    code = args.func(args)
    _ = capsys.readouterr()

    assert code == 0

    docs_architecture = (
        tmp_path / "docs" / "references" / "docs-architecture-llms.md"
    ).read_text(encoding="utf-8")
    workflow_reference = (
        tmp_path / "docs" / "references" / "workflow-llms.md"
    ).read_text(encoding="utf-8")

    assert "Audience Split" in docs_architecture
    assert "README.md" in docs_architecture
    assert "AGENTS.md" in docs_architecture
    assert "engineeringagent validate" in workflow_reference
    assert "engineeringagent gates run --profile precommit" in workflow_reference

    assert not (tmp_path / "docs" / "principles").exists()
    assert not (tmp_path / "docs" / "fitness-functions").exists()
