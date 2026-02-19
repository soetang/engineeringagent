from __future__ import annotations

from importlib.resources import files
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest
import yaml
from typer.testing import CliRunner

from engineeringagent.agents import build_backend_scaffold_manifest
from engineeringagent import cli as cli_module
from engineeringagent.init_scaffold import (
    _spec_validate_gate,
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


def test_init_help_documents_model_option() -> None:
    """Verify init help keeps --model docs backend-agnostic."""
    result = _invoke_cli(["init", "--help"])

    assert result.exit_code == 0
    assert "--model" in result.stdout
    assert "openai/gpt-5.3-codex" in result.stdout
    assert "OpenCode" not in result.stdout
    assert ".opencode/" not in result.stdout


def test_init_model_flag_controls_scaffolded_opencode_agent(
    tmp_path: Path,
) -> None:
    """Verify --model pins the scaffolded OpenCode agent model."""
    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "--no-precommit-install",
            "--model",
            "openai/gpt-5.3-codex-spark",
        ]
    )

    assert result.exit_code == 0
    agent_path = tmp_path / ".opencode" / "agents" / "engineeringagent.md"
    assert agent_path.exists()
    payload = agent_path.read_text(encoding="utf-8")
    model_lines = [
        line for line in payload.splitlines() if line.lstrip().startswith("model:")
    ]
    assert len(model_lines) == 1
    assert "openai/gpt-5.3-codex-spark" in model_lines[0]


def test_init_defaults_to_slim_pack_without_prompting_in_non_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init defaults to slim without prompting when not a TTY."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: False)
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
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "standard")

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "pack=standard" in result.stdout


def test_init_pack_arg_never_prompts_even_on_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify providing the pack positional disables the interactive prompt."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: pytest.fail("init prompted unexpectedly"),
    )

    result = _invoke_cli(["--project-root", str(tmp_path), "init", "slim"])

    assert result.exit_code == 0
    assert "pack=slim" in result.stdout


def test_init_backend_option_skips_prompt_even_on_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify explicit --backend disables interactive backend prompt."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(
        cli_module,
        "list_backends",
        lambda: ("opencode", "mock-b"),
    )
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: pytest.fail("init prompted unexpectedly"),
    )

    result = _invoke_cli(
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

    assert result.exit_code == 0


def test_init_prompts_for_backend_when_omitted_and_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init prompts for backend selection when omitted in a TTY."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(
        cli_module,
        "list_backends",
        lambda: ("zeta", "opencode", "alpha"),
    )
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")

    prompts: list[str] = []

    def _fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "opencode"

    monkeypatch.setattr("builtins.input", _fake_input)

    result = _invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    assert prompts == [
        "init backend: choose [alpha/opencode/zeta] (default opencode): "
    ]


def test_init_backend_prompt_invalid_input_returns_deterministic_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid backend prompt input exits with deterministic error text."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(
        cli_module,
        "list_backends",
        lambda: ("zeta", "opencode", "alpha"),
    )
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")
    monkeypatch.setattr("builtins.input", lambda _prompt: "invalid")

    result = _invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 1
    assert (
        "init input error: backend must be one of: alpha, opencode, zeta"
        in result.stdout
    )


def test_init_backend_prompt_uses_default_on_eof(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify backend prompt falls back to default when stdin is closed (EOF)."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(
        cli_module,
        "list_backends",
        lambda: ("opencode", "mock-b"),
    )
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")

    def _raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)

    result = _invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    toml_text = (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    assert '[agents]\nbackend = "opencode"\n' in toml_text


def test_init_backend_uses_existing_config_without_prompt_unless_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify existing backend config skips prompt unless --force is used."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(
        cli_module,
        "list_backends",
        lambda: ("opencode", "mock-b"),
    )
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")

    no_force_root = tmp_path / "no_force"
    no_force_root.mkdir()
    (no_force_root / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "opencode"\n',
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: pytest.fail("init prompted unexpectedly"),
    )

    no_force = _invoke_cli(
        [
            "--project-root",
            str(no_force_root),
            "init",
            "slim",
            "--no-precommit-install",
        ]
    )
    assert no_force.exit_code == 0
    assert (no_force_root / "engineeringagent.toml").read_text(encoding="utf-8") == (
        '[agents]\nbackend = "opencode"\n'
    )
    assert (no_force_root / ".opencode" / "agents" / "engineeringagent.md").exists()

    force_root = tmp_path / "force"
    force_root.mkdir()
    (force_root / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "mock-b"\n',
        encoding="utf-8",
    )

    prompts: list[str] = []

    def _force_input(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", _force_input)
    forced = _invoke_cli(
        [
            "--project-root",
            str(force_root),
            "init",
            "slim",
            "--force",
            "--no-precommit-install",
        ]
    )
    assert forced.exit_code == 0
    assert prompts == ["init backend: choose [mock-b/opencode] (default opencode): "]
    assert (force_root / "engineeringagent.toml").read_text(encoding="utf-8") == (
        '[agents]\nbackend = "opencode"\n'
    )
    assert (force_root / ".opencode" / "agents" / "engineeringagent.md").exists()


def test_init_backend_selects_single_backend_without_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init auto-selects when only one backend is registered."""
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: True)
    monkeypatch.setattr(cli_module, "list_backends", lambda: ("opencode",))
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")
    monkeypatch.setattr(
        "builtins.input",
        lambda _prompt: pytest.fail("init prompted unexpectedly"),
    )

    result = _invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    toml_text = (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    assert '[agents]\nbackend = "opencode"\n' in toml_text


def test_spec_validate_gate_helper_builds_expected_patterns() -> None:
    """Verify init scaffold shares a single spec_validate gate shape."""

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
        'docs-root = "docs.engineeringagent"\n\n[agents]\nbackend = "opencode"\n'
    )


def test_init_writes_backend_to_engineeringagent_toml_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init persists selected backend when config file is missing."""
    monkeypatch.setattr(cli_module, "list_backends", lambda: ("opencode", "mock-b"))
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: False)

    result = _invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    assert (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8") == (
        '[agents]\nbackend = "opencode"\n'
    )


def test_init_explicit_non_default_backend_persists_to_engineeringagent_toml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify explicit non-default --backend persists on a fresh init run."""
    monkeypatch.setattr(cli_module, "list_backends", lambda: ("opencode", "mock-b"))
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "mock-b")
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: False)

    result = _invoke_cli(
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

    assert result.exit_code == 0
    assert (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8") == (
        '[agents]\nbackend = "opencode"\n'
    )
    assert (tmp_path / ".opencode" / "agents" / "engineeringagent.md").exists()


def test_init_appends_backend_to_existing_engineeringagent_toml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init appends [agents].backend when config exists without it."""
    monkeypatch.setattr(cli_module, "list_backends", lambda: ("opencode", "mock-b"))
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: False)

    config_path = tmp_path / "engineeringagent.toml"
    config_path.write_text('docs-root = "docs.engineeringagent"\n', encoding="utf-8")

    result = _invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    assert config_path.read_text(encoding="utf-8") == (
        'docs-root = "docs.engineeringagent"\n\n[agents]\nbackend = "opencode"\n'
    )


def test_init_preserves_existing_backend_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init does not overwrite existing backend unless --force is used."""
    monkeypatch.setattr(cli_module, "list_backends", lambda: ("opencode", "mock-b"))
    monkeypatch.setattr(cli_module, "default_backend_id", lambda: "opencode")
    monkeypatch.setattr(cli_module, "_stdout_is_tty", lambda: False)

    config_path = tmp_path / "engineeringagent.toml"
    config_path.write_text('[agents]\nbackend = "mock-b"\n', encoding="utf-8")

    result = _invoke_cli(
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

    assert result.exit_code == 0
    assert config_path.read_text(encoding="utf-8") == '[agents]\nbackend = "mock-b"\n'


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
    assert "harness/checks.yaml" in scaffold_agents
    assert "engineeringagent run --all" in scaffold_agents


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
    """Verify init writes pre-commit wiring and harness/checks.yaml."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0

    precommit_config = (tmp_path / ".pre-commit-config.yaml").read_text(
        encoding="utf-8"
    )
    assert (
        "entry: engineeringagent checks run --phase iteration_end" in precommit_config
    )
    assert "uvx --from . engineeringagent" not in precommit_config
    assert "engineeringagent-commit-msg" not in precommit_config

    assert not (tmp_path / "harness" / "gates.yaml").exists()
    assert not (tmp_path / "harness" / "reviewers.yaml").exists()

    checks_config = yaml.safe_load(
        (tmp_path / "harness" / "checks.yaml").read_text(encoding="utf-8")
    )
    assert checks_config["contract_version"] == "1.0"
    assert checks_config["defaults"]["when"]["phase"] == "iteration_end"
    assert checks_config["checks"] == {}

    fitness_manifest = yaml.safe_load(
        (tmp_path / "harness" / "fitness-functions" / "rules.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert fitness_manifest["contract_version"] == "1.0"
    assert not fitness_manifest["rules"]


def test_init_attempts_precommit_install_when_git_repo_and_precommit_available(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init best-effort installs pre-commit hooks when possible."""
    (tmp_path / ".git").mkdir(parents=True)
    calls: list[tuple[Path, str | None]] = []

    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _fake_precommit_install(
        project_root: Path,
        *,
        hook_type: str | None = None,
    ) -> object:
        calls.append((project_root, hook_type))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        cli_module.git_client, "precommit_install", _fake_precommit_install
    )

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert calls == [(tmp_path.resolve(), None)]


def test_init_attempts_precommit_install_when_git_marker_is_file(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init treats worktree-style .git files as git repos."""
    (tmp_path / ".git").write_text("gitdir: /tmp/gitdir\n", encoding="utf-8")
    calls: list[tuple[Path, str | None]] = []

    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _fake_precommit_install(
        project_root: Path,
        *,
        hook_type: str | None = None,
    ) -> object:
        calls.append((project_root, hook_type))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        cli_module.git_client, "precommit_install", _fake_precommit_install
    )

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert calls == [(tmp_path.resolve(), None)]


def test_init_python_uv_attempts_commit_msg_hook_install(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify python_uv init attempts installing the commit-msg hook type."""
    (tmp_path / ".git").mkdir(parents=True)
    calls: list[tuple[Path, str | None]] = []

    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _fake_precommit_install(
        project_root: Path,
        *,
        hook_type: str | None = None,
    ) -> object:
        calls.append((project_root, hook_type))
        return SimpleNamespace(returncode=0, stdout="", stderr="")

    monkeypatch.setattr(
        cli_module.git_client, "precommit_install", _fake_precommit_install
    )

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
    assert calls == [
        (tmp_path.resolve(), None),
        (tmp_path.resolve(), "commit-msg"),
    ]


def test_init_non_git_repo_prints_precommit_remediation_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init hints how to wire hooks when not in a git repo."""
    monkeypatch.setattr(
        cli_module.git_client,
        "precommit_install",
        lambda *_args, **_kwargs: pytest.fail("unexpected pre-commit install attempt"),
    )

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "skipped pre-commit hook install" in result.stdout
    assert "git init" in result.stdout
    assert "pre-commit install" in result.stdout


def test_init_missing_precommit_prints_remediation_hint(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init succeeds and hints when pre-commit is missing."""
    (tmp_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: None)
    monkeypatch.setattr(
        cli_module.git_client,
        "precommit_install",
        lambda *_args, **_kwargs: pytest.fail("unexpected pre-commit install attempt"),
    )

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "skipped pre-commit hook install" in result.stdout
    assert "pre-commit not found" in result.stdout
    assert "pre-commit install" in result.stdout


def test_init_precommit_install_failure_is_non_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init does not fail solely due to hook installation failure."""
    (tmp_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _fake_precommit_install(
        _project_root: Path,
        *,
        hook_type: str | None = None,
    ) -> object:
        assert hook_type is None
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(
        cli_module.git_client, "precommit_install", _fake_precommit_install
    )

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "init warning" in result.stdout
    assert "exit_code=1" in result.stdout
    assert "pre-commit install" in result.stdout


def test_init_precommit_install_exception_is_non_fatal(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init survives unexpected subprocess errors during hook install."""
    (tmp_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")

    def _boom(_project_root: Path, *, hook_type: str | None = None) -> object:  # noqa: ARG001
        raise FileNotFoundError("pre-commit")

    monkeypatch.setattr(cli_module.git_client, "precommit_install", _boom)

    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "init warning" in result.stdout
    assert "error=FileNotFoundError" in result.stdout
    assert "pre-commit install" in result.stdout


def test_init_no_precommit_install_flag_skips_install_attempts(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify --no-precommit-install disables all hook installation attempts."""
    (tmp_path / ".git").mkdir(parents=True)
    monkeypatch.setattr(cli_module.shutil, "which", lambda _name: "/bin/pre-commit")
    monkeypatch.setattr(
        cli_module.git_client,
        "precommit_install",
        lambda *_args, **_kwargs: pytest.fail("unexpected pre-commit install attempt"),
    )

    result = _invoke_cli(
        ["--project-root", str(tmp_path), "init", "--no-precommit-install"]
    )

    assert result.exit_code == 0


def test_init_slim_pack_does_not_scaffold_demo_failure(tmp_path: Path) -> None:
    """Verify slim pack scaffolds validations without demo failing rule wiring."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init", "slim"])

    assert result.exit_code == 0
    assert "pack=slim" in result.stdout

    assert not (tmp_path / "harness" / "gates.yaml").exists()
    assert not (tmp_path / "harness" / "reviewers.yaml").exists()
    assert not (
        tmp_path / "harness" / "fitness-functions" / "demo_always_fail.py"
    ).exists()

    checks_config = yaml.safe_load(
        (tmp_path / "harness" / "checks.yaml").read_text(encoding="utf-8")
    )
    assert checks_config["contract_version"] == "1.0"
    assert checks_config["checks"] == {}


def test_init_standard_pack_scaffolds_demo_failing_fitness_rule(
    tmp_path: Path,
) -> None:
    """Verify standard pack wires an always-failing demo fitness rule."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init", "standard"])

    assert result.exit_code == 0
    assert "pack=standard" in result.stdout
    assert "demo failing" in result.stdout.lower()

    assert not (tmp_path / "harness" / "gates.yaml").exists()
    assert not (tmp_path / "harness" / "reviewers.yaml").exists()

    demo_script_path = (
        tmp_path / "harness" / "fitness-functions" / "demo_always_fail.py"
    )
    assert demo_script_path.exists()

    baseline_manifest = yaml.safe_load(
        (tmp_path / "harness" / "fitness-functions" / "rules.yaml").read_text(
            encoding="utf-8"
        )
    )

    assert baseline_manifest["contract_version"] == "1.0"
    assert [rule["rule_id"] for rule in baseline_manifest["rules"]] == [
        "demo.always-fail"
    ]

    checks_config = yaml.safe_load(
        (tmp_path / "harness" / "checks.yaml").read_text(encoding="utf-8")
    )
    assert checks_config["contract_version"] == "1.0"
    assert checks_config["checks"]["fitness_all"]["type"] == "fitness"


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
    assert (
        "entry: engineeringagent checks run --phase iteration_end" in precommit_config
    )
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
        "entry: uv run engineeringagent checks run --phase iteration_end"
        in precommit_config
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

    assert not (tmp_path / "harness" / "gates.yaml").exists()


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
    backend_template_dir = files(
        "engineeringagent.agents.backends.opencode.scaffold_templates"
    )
    manifest = build_baseline_scaffold_manifest(profile="core")

    assert manifest[".pre-commit-config.yaml"] == template_dir.joinpath(
        "precommit.core.yaml"
    ).read_text(encoding="utf-8")
    assert manifest["AGENTS.md"] == template_dir.joinpath("AGENTS.md").read_text(
        encoding="utf-8"
    )

    backend_template_files = {
        entry.name for entry in backend_template_dir.iterdir() if entry.is_file()
    }
    assert "agent.engineeringagent.md" in backend_template_files
    assert "gitignore" in backend_template_files

    assert ".opencode/agents/engineeringagent.md" in manifest
    assert ".opencode/.gitignore" in manifest
    assert manifest[".opencode/.gitignore"] == backend_template_dir.joinpath(
        "gitignore"
    ).read_text(encoding="utf-8")


def test_build_baseline_scaffold_manifest_includes_opencode_policy_files() -> None:
    """Verify init manifest includes deterministic OpenCode agent policy outputs."""
    manifest = build_baseline_scaffold_manifest(profile="core")

    assert ".opencode/agents/engineeringagent.md" in manifest
    assert manifest[".opencode/agents/engineeringagent.md"]

    backend_template_dir = files(
        "engineeringagent.agents.backends.opencode.scaffold_templates"
    )
    assert manifest[".opencode/.gitignore"] == backend_template_dir.joinpath(
        "gitignore"
    ).read_text(encoding="utf-8")


def test_build_baseline_scaffold_manifest_composes_backend_manifest() -> None:
    """Verify baseline scaffold includes real backend manifest entries."""

    expected_backend_manifest = build_backend_scaffold_manifest(
        backend_id="opencode",
        agent_model="openai/gpt-5.3-codex-spark",
    )

    manifest = build_baseline_scaffold_manifest(
        profile="core",
        backend_id="opencode",
        agent_model="openai/gpt-5.3-codex-spark",
    )

    for path, content in expected_backend_manifest.items():
        assert manifest[path] == content
    assert ".pre-commit-config.yaml" in manifest


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
    assert "engineeringagent run --all" in workflow_reference

    assert not (tmp_path / "docs" / "principles").exists()
    assert not (tmp_path / "docs" / "fitness-functions").exists()


def test_init_scaffolds_spec_writing_reference_doc(tmp_path: Path) -> None:
    """Verify init scaffolds the spec-writing reference doc."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0

    spec_writing_reference = (
        tmp_path / "docs" / "references" / "spec-writing-llms.md"
    ).read_text(encoding="utf-8")
    assert "Spec Writing Guide" in spec_writing_reference
    assert "Mandatory Interview Flow" in spec_writing_reference


def test_init_scaffolds_scaffold_policy_with_resolved_docs_root(tmp_path: Path) -> None:
    """Verify init creates scaffold_policy.yaml with docs_root aligned to docs_dir."""
    result = _invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0

    policy_path = tmp_path / "harness" / "scaffold_policy.yaml"
    assert policy_path.exists()

    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    assert payload["contract_version"] == "1.0"
    assert payload["docs_root"] == "docs"
    assert not payload["human_docs"]
    assert payload["agent_docs"] == [
        "docs/references/docs-architecture-llms.md",
        "docs/references/spec-writing-llms.md",
        "docs/references/workflow-llms.md",
    ]


def test_init_separate_docs_updates_scaffold_policy_docs_root(tmp_path: Path) -> None:
    """Verify init separate docs mode sets scaffold policy docs_root to selected dir."""
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

    policy_path = tmp_path / "harness" / "scaffold_policy.yaml"
    payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    assert payload["docs_root"] == "docs.engineeringagent"
    assert isinstance(payload["human_docs"], list)
    assert isinstance(payload["agent_docs"], list)
