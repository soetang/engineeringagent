from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
from engineeringagent.init_scaffold import (
    build_baseline_scaffold_manifest,
    build_scaffold_agents_markdown,
)


def _invoke_cli(args: list[str]) -> Any:
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def test_init_subcommand_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Typer routes the init command to the init handler."""
    recorded: dict[str, object] = {}

    def _fake_cmd_init(args: Any) -> int:
        recorded["project_root"] = args.project_root
        return 0

    monkeypatch.setattr(cli_module, "cmd_init", _fake_cmd_init)
    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert recorded == {"project_root": str(tmp_path)}


def test_init_rejects_include_reviewers_flag() -> None:
    """Verify init no longer accepts the removed include-reviewers flag."""
    result = _invoke_cli(["init", "--include-reviewers"])

    assert result.exit_code == 2
    assert "No such option: --include-reviewers" in result.stderr


def test_init_defaults_to_slim_pack_without_prompting_in_non_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init defaults to slim without prompting when not a TTY."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: False, raising=False)
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: pytest.fail("init prompted unexpectedly"),
    )

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "pack=slim" in result.stdout


def test_init_prompts_for_pack_when_omitted_and_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init prompts for pack selection when omitted in a TTY."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True, raising=False)
    monkeypatch.setattr("builtins.input", lambda _prompt: "standard")

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "pack=standard" in result.stdout


def test_init_pack_arg_never_prompts_even_on_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify providing the pack positional disables the interactive prompt."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True, raising=False)
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: pytest.fail("init prompted unexpectedly"),
    )

    result = _invoke_cli(["--project-root", str(tmp_path), "init", "slim"])

    assert result.exit_code == 0
    assert "pack=slim" in result.stdout


def test_spec_validate_gate_helper_builds_expected_patterns() -> None:
    """Verify init scaffold shares a single spec_validate gate shape."""

    from engineeringagent.init_scaffold import _spec_validate_gate

    assert _spec_validate_gate("docs") == {
        "run": "engineeringagent validate",
        "on_change": [
            "docs/spec/**/*.yaml",
            "docs/spec/**/*.yml",
            "docs/spec/**/*.json",
        ],
    }


def test_init_prompts_when_docs_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init prompts for docs conflict and supports reuse mode."""
    (tmp_path / "docs").mkdir(parents=True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "reuse")

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "docs_dir=docs" in result.stdout
    assert (tmp_path / "docs" / "spec" / "features" / ".gitkeep").exists()


def test_init_can_use_separate_docs_directory(tmp_path: Path) -> None:
    """Verify init can scaffold into a distinct docs directory."""
    (tmp_path / "docs").mkdir(parents=True)

    result = _invoke_cli(
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

    assert result.exit_code == 0
    assert "docs_dir=docs.engineeringagent" in result.stdout
    assert not (tmp_path / "docs" / "spec").exists()
    assert (
        tmp_path / "docs.engineeringagent" / "spec" / "features" / ".gitkeep"
    ).exists()


def test_init_separate_docs_writes_engineeringagent_toml_docs_root(
    tmp_path: Path,
) -> None:
    """Verify init separate docs mode writes docs-root to engineeringagent.toml."""
    (tmp_path / "docs").mkdir(parents=True)

    result = _invoke_cli(
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

    assert result.exit_code == 0
    assert "docs_dir=docs.engineeringagent" in result.stdout
    assert (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8") == (
        'docs-root = "docs.engineeringagent"\n'
    )


def test_validate_and_run_all_use_separate_docs_root(
    tmp_path: Path,
) -> None:
    """Verify separate docs-root config is honored by validate and run --all."""
    (tmp_path / "docs").mkdir(parents=True)

    init_result = _invoke_cli(
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
    assert init_result.exit_code == 0

    feature_path = (
        tmp_path
        / "docs.engineeringagent"
        / "spec"
        / "features"
        / "FEAT-950-separate-docs-root.yaml"
    )
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-950",
                "title": "Separate docs root runtime smoke test",
                "type": "feature",
                "expected_commit_subject": "feat: test separate docs root runtime support",
                "status": "backlog",
                "priority": "high",
                "objective": "Validate and run-all consume configured separate docs root.",
                "acceptance": ["Separate docs root is honored by runtime commands."],
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    validate_result = _invoke_cli(["--project-root", str(tmp_path), "validate"])

    assert validate_result.exit_code == 0
    assert "spec validation: ok" in validate_result.stdout

    run_result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "run",
            "--all",
            "--dry-run",
            "--skip-implement",
        ]
    )

    assert run_result.exit_code == 0
    assert "[dry-run] Resolved 1 feature file(s)." in run_result.stdout
    assert "feature=FEAT-950" in run_result.stdout
    assert (
        "docs.engineeringagent/spec/features/FEAT-950-separate-docs-root.yaml"
        in run_result.stdout
    )


def test_init_agents_conflict_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init can explicitly overwrite an existing AGENTS.md."""
    (tmp_path / "AGENTS.md").write_text("user guidance\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "overwrite")

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "agents_mode=overwrite" in result.stdout
    scaffold_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert "user guidance" not in scaffold_agents
    assert "engineeringagent validate" in scaffold_agents


def test_init_agents_conflict_preserve_and_create_merge_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify preserve mode renames AGENTS and creates a merge follow-up spec."""
    (tmp_path / "AGENTS.md").write_text("legacy guidance\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "preserve")

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "agents_mode=preserve" in result.stdout
    assert "agents_backup=AGENTS.user.md" in result.stdout

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


def test_init_agents_conflict_abort(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify abort mode keeps AGENTS and exits without scaffold writes."""
    (tmp_path / "AGENTS.md").write_text("do not touch\n", encoding="utf-8")
    monkeypatch.setattr("builtins.input", lambda _prompt: "abort")

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "init aborted" in result.stdout
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
) -> None:
    """Verify init writes pre-commit wiring, gate stubs, and fitness declarations."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0

    precommit_config = (tmp_path / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert "entry: engineeringagent gates run --profile precommit" in precommit_config
    assert "uvx --from . engineeringagent" not in precommit_config
    assert "engineeringagent-commit-msg" not in precommit_config

    gates_config = yaml.safe_load(
        (tmp_path / "harness" / "gates.yaml").read_text(encoding="utf-8")
    )
    assert gates_config["profiles"]["precommit"] == ["spec_validate"]
    assert gates_config["profiles"]["loop_fast"] == ["spec_validate"]
    assert gates_config["gates"]["spec_validate"]["run"] == "engineeringagent validate"

    fitness_manifest = yaml.safe_load(
        (tmp_path / "harness" / "fitness-functions" / "rules.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert fitness_manifest["contract_version"] == "1.0"
    assert [rule["rule_id"] for rule in fitness_manifest["rules"]] == [
        "architecture.dep-directionality",
        "architecture.loop-subprocess-boundary",
        "architecture.scaffold-template-locality",
    ]
    assert all(rule["adapter"] == "command" for rule in fitness_manifest["rules"])


def test_init_slim_pack_does_not_scaffold_demo_failure(tmp_path: Path) -> None:
    """Verify slim pack scaffolds validations without demo failing rule wiring."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init", "slim"])

    assert result.exit_code == 0
    assert "pack=slim" in result.stdout

    gates_config = yaml.safe_load(
        (tmp_path / "harness" / "gates.yaml").read_text(encoding="utf-8")
    )
    assert gates_config["profiles"]["precommit"] == ["spec_validate"]
    assert "demo_fail" not in gates_config["gates"]

    assert not (tmp_path / "harness" / "fitness-functions" / "demo_rules.yaml").exists()
    assert not (
        tmp_path / "harness" / "fitness-functions" / "demo_always_fail.py"
    ).exists()


def test_init_standard_pack_scaffolds_demo_fail_gate_and_manifest(
    tmp_path: Path,
) -> None:
    """Verify standard pack wires an always-failing demo fitness rule into precommit."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init", "standard"])

    assert result.exit_code == 0
    assert "pack=standard" in result.stdout
    assert "demo failing" in result.stdout.lower()

    gates_config = yaml.safe_load(
        (tmp_path / "harness" / "gates.yaml").read_text(encoding="utf-8")
    )
    assert gates_config["profiles"]["precommit"] == ["spec_validate", "demo_fail"]
    assert (
        gates_config["gates"]["demo_fail"]["run"]
        == "engineeringagent fitness run --format json --manifest-path harness/fitness-functions/demo_rules.yaml"
    )

    demo_manifest_path = tmp_path / "harness" / "fitness-functions" / "demo_rules.yaml"
    assert demo_manifest_path.exists()
    demo_manifest = yaml.safe_load(demo_manifest_path.read_text(encoding="utf-8"))
    assert demo_manifest["contract_version"] == "1.0"
    assert [rule["rule_id"] for rule in demo_manifest["rules"]] == ["demo.always-fail"]

    demo_script_path = (
        tmp_path / "harness" / "fitness-functions" / "demo_always_fail.py"
    )
    assert demo_script_path.exists()

    baseline_manifest = yaml.safe_load(
        (tmp_path / "harness" / "fitness-functions" / "rules.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert "demo.always-fail" not in [
        rule["rule_id"] for rule in baseline_manifest["rules"]
    ]


def test_init_defaults_to_core_language_agnostic_profile(
    tmp_path: Path,
) -> None:
    """Verify init defaults to the language-agnostic core scaffold profile."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "profile=core" in result.stdout

    precommit_config = (tmp_path / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert "entry: engineeringagent gates run --profile precommit" in precommit_config
    assert "uvx --from ." not in precommit_config
    assert "engineeringagent-commit-msg" not in precommit_config


def test_init_python_uv_profile_available(tmp_path: Path) -> None:
    """Verify init supports the optional python_uv scaffold profile."""
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--scaffold-profile",
            "python_uv",
        ]
    )

    assert result.exit_code == 0
    assert "profile=python_uv" in result.stdout

    precommit_config = (tmp_path / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert (
        "entry: uvx engineeringagent gates run --profile precommit" in precommit_config
    )
    assert "uvx --from ." not in precommit_config
    assert "engineeringagent-commit-msg" in precommit_config
    assert (
        "harness/fitness-functions/validate_commit_messages.py --commit-msg-file"
        in precommit_config
    )

    commit_msg_script = (
        tmp_path / "harness" / "fitness-functions" / "validate_commit_messages.py"
    )
    assert commit_msg_script.exists()
    commit_msg_script_text = commit_msg_script.read_text(encoding="utf-8")
    assert "--commit-msg-file" in commit_msg_script_text
    assert "engineeringagent" not in commit_msg_script_text


def test_python_uv_commit_msg_validator_avoids_subprocess(tmp_path: Path) -> None:
    """Verify scaffolded commit-msg validator does not use subprocess."""
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--scaffold-profile",
            "python_uv",
        ]
    )

    assert result.exit_code == 0

    commit_msg_script = (
        tmp_path / "harness" / "fitness-functions" / "validate_commit_messages.py"
    )
    commit_msg_script_text = commit_msg_script.read_text(encoding="utf-8")
    assert "import subprocess" not in commit_msg_script_text
    assert "subprocess." not in commit_msg_script_text

    gates_config = yaml.safe_load(
        (tmp_path / "harness" / "gates.yaml").read_text(encoding="utf-8")
    )
    assert gates_config["profiles"]["precommit"] == ["spec_validate", "ruff_validate"]
    assert "ruff_validate" in gates_config["gates"]
    assert (
        gates_config["gates"]["ruff_validate"]["run"] == "uvx ruff check --isolated ."
    )
    assert "pyright_validate" not in gates_config["gates"]


def test_python_uv_commit_msg_validator_builds_pattern_from_allowed_types(
    tmp_path: Path,
) -> None:
    """Verify scaffolded commit-msg validator keeps types/regex in sync."""
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--scaffold-profile",
            "python_uv",
        ]
    )

    assert result.exit_code == 0

    commit_msg_script = (
        tmp_path / "harness" / "fitness-functions" / "validate_commit_messages.py"
    )
    commit_msg_script_text = commit_msg_script.read_text(encoding="utf-8")
    assert "ALLOWED_COMMIT_TYPES" in commit_msg_script_text
    assert "_ALLOWED_TYPES_PATTERN" in commit_msg_script_text
    assert "re.escape" in commit_msg_script_text
    assert "COMMIT_SUBJECT_PATTERN" in commit_msg_script_text
    assert "(feat|fix|spec|docs|chore|test)" not in commit_msg_script_text


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

    assert template_dir.joinpath("opencode.agent.engineeringagent.md").read_text(
        encoding="utf-8"
    ) == (
        "---\n"
        "description: Build agent override for deterministic repository automation.\n"
        "mode: primary\n"
        'model: "openai/gpt-5.3-codex"\n'
        "variant: 'high'\n"
        "permission:\n"
        '  "*": allow\n'
        "  bash: allow\n"
        "---\n"
    )

    assert (
        template_dir.joinpath("opencode.gitignore").read_text(encoding="utf-8")
        == "node_modules\npackage.json\nbun.lock\n.gitignore\n"
    )


def test_build_baseline_scaffold_manifest_includes_opencode_policy_files() -> None:
    """Verify init manifest includes deterministic OpenCode agent policy outputs."""
    template_dir = files("engineeringagent.scaffold_templates")
    manifest = build_baseline_scaffold_manifest(profile="core")

    assert manifest[".opencode/agents/engineeringagent.md"] == template_dir.joinpath(
        "opencode.agent.engineeringagent.md"
    ).read_text(encoding="utf-8")
    assert manifest[".opencode/.gitignore"] == template_dir.joinpath(
        "opencode.gitignore"
    ).read_text(encoding="utf-8")


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


def test_init_scaffolds_tool_generic_docs_only(tmp_path: Path) -> None:
    """Verify init scaffolds reusable tool docs without repo-internal docs."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0

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
