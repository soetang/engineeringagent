from __future__ import annotations

import io
from pathlib import Path

import pytest

from engineeringagent.presentation.cli import init as cli_init_module
from engineeringagent import init_cli_support
from tests.presentation.cli.init_command_support import (
    DEFAULT_LAUNCHER_ARGS,
    fail_on_input,
    init_args,
    invoke_cli,
    patch_non_tty,
    patch_tty,
    tomllib,
)


def load_engineeringagent_config(project_root: Path) -> dict[str, object]:
    """Parse the persisted engineeringagent.toml for behavior-level assertions."""
    return tomllib.loads(
        (project_root / "engineeringagent.toml").read_text(encoding="utf-8")
    )


def test_init_backend_option_skips_prompt_even_on_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify explicit --backend disables interactive backend prompt."""
    patch_tty(monkeypatch, backends=("opencode", "mock-b"), default_backend="opencode")
    fail_on_input(monkeypatch)

    result = invoke_cli(
        init_args(tmp_path, "slim", "--backend", "opencode", *DEFAULT_LAUNCHER_ARGS)
    )

    assert result.exit_code == 0


def test_init_prompts_for_backend_when_omitted_and_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init prompts for backend selection when omitted in a TTY."""
    patch_tty(monkeypatch, backends=("zeta", "opencode", "alpha"), default_backend="opencode")
    prompts: list[str] = []

    def _fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return "opencode" if "init backend:" in prompt else ""

    monkeypatch.setattr("builtins.input", _fake_input)
    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    assert len(prompts) == 2
    assert "init backend:" in prompts[0]
    assert "alpha/opencode/zeta" in prompts[0]
    assert "AGENTS launcher" in prompts[1]


def test_init_backend_prompt_invalid_input_returns_deterministic_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid backend prompt input exits with deterministic error text."""
    patch_tty(monkeypatch, backends=("zeta", "opencode", "alpha"), default_backend="opencode")
    monkeypatch.setattr("builtins.input", lambda _prompt: "invalid")

    result = invoke_cli(
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
    patch_tty(monkeypatch, backends=("opencode", "mock-b"), default_backend="opencode")

    def _raise_eof(_prompt: str) -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise_eof)
    result = invoke_cli(
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
    patch_tty(monkeypatch, backends=("opencode", "mock-b"), default_backend="opencode")

    no_force_root = tmp_path / "no_force"
    no_force_root.mkdir()
    (no_force_root / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "opencode"\n',
        encoding="utf-8",
    )
    fail_on_input(monkeypatch)

    no_force = invoke_cli(init_args(no_force_root, "slim", *DEFAULT_LAUNCHER_ARGS))
    assert no_force.exit_code == 0
    assert load_engineeringagent_config(no_force_root) == {"agents": {"backend": "opencode"}}
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
    forced = invoke_cli(
        init_args(force_root, "slim", "--force", *DEFAULT_LAUNCHER_ARGS)
    )
    assert forced.exit_code == 0
    assert prompts == ["init backend: choose [mock-b/opencode] (default opencode): "]
    assert load_engineeringagent_config(force_root) == {"agents": {"backend": "opencode"}}
    assert (force_root / ".opencode" / "agents" / "engineeringagent.md").exists()


def test_init_backend_selects_single_backend_without_prompt(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init auto-selects when only one backend is registered."""
    patch_tty(monkeypatch, backends=("opencode",), default_backend="opencode")
    fail_on_input(monkeypatch)

    result = invoke_cli(init_args(tmp_path, "slim", *DEFAULT_LAUNCHER_ARGS))

    assert result.exit_code == 0
    toml_text = (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    assert '[agents]\nbackend = "opencode"\n' in toml_text


def test_init_prompts_when_docs_exists(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init prompts for docs conflict and supports reuse mode."""
    (tmp_path / "docs").mkdir(parents=True)
    monkeypatch.setattr("builtins.input", lambda _prompt: "reuse")

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "docs_dir=docs" in result.stdout
    assert (tmp_path / "docs" / "spec" / "features" / ".gitkeep").exists()


def test_init_can_use_separate_docs_directory(tmp_path: Path) -> None:
    """Verify init can scaffold into a distinct docs directory."""
    (tmp_path / "docs").mkdir(parents=True)

    result = invoke_cli(
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

    result = invoke_cli(
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
    assert load_engineeringagent_config(tmp_path) == {
        "docs-root": "docs.engineeringagent",
        "agents": {"backend": "opencode"},
    }


def test_init_writes_backend_to_engineeringagent_toml_when_missing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init persists selected backend when config file is missing."""
    monkeypatch.setattr(
        cli_init_module, "list_backends", lambda: ("opencode", "mock-b")
    )
    monkeypatch.setattr(cli_init_module, "default_backend_id", lambda: "opencode")
    patch_non_tty(monkeypatch)

    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    assert load_engineeringagent_config(tmp_path) == {"agents": {"backend": "opencode"}}


def test_init_explicit_non_default_backend_persists_to_engineeringagent_toml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify explicit non-default --backend persists on a fresh init run."""
    monkeypatch.setattr(
        cli_init_module, "list_backends", lambda: ("opencode", "mock-b")
    )
    monkeypatch.setattr(cli_init_module, "default_backend_id", lambda: "mock-b")
    patch_non_tty(monkeypatch)

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

    assert result.exit_code == 0
    assert load_engineeringagent_config(tmp_path) == {"agents": {"backend": "opencode"}}
    assert (tmp_path / ".opencode" / "agents" / "engineeringagent.md").exists()


def test_init_prompt_helpers_follow_active_stdout(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify prompt helpers consult the active stdout stream at call time."""
    active_stdout = io.StringIO()
    monkeypatch.setattr(init_cli_support.sys, "stdout", active_stdout)

    prompt_context = init_cli_support.InitPromptContext(
        stdout_is_tty_fn=lambda stream: stream is init_cli_support.sys.stdout
    )
    selected_pack, pack_error = init_cli_support.resolve_init_pack(
        None,
        input_fn=lambda _prompt: "",
        stdout_is_tty_fn=lambda stream: stream is init_cli_support.sys.stdout,
    )
    selected_backend, backend_error = init_cli_support.resolve_init_backend(
        project_root=tmp_path,
        backend=None,
        force=True,
        deps=init_cli_support.InitBackendResolverDeps(
            list_backends_fn=lambda: ("codex", "opencode"),
            default_backend_id_fn=lambda: "opencode",
            resolve_agents_backend_id_fn=lambda _root: None,
        ),
    )

    assert prompt_context.is_tty() is True
    assert (selected_pack, pack_error) == ("slim", None)
    assert (selected_backend, backend_error) == ("opencode", None)


def test_validate_and_run_all_use_separate_docs_root(tmp_path: Path) -> None:
    """Verify separate docs-root config is honored by validate and run --all."""
    import yaml

    (tmp_path / "docs").mkdir(parents=True)
    init_result = invoke_cli(
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
        / "FEAT-950-separate-docs-root"
        / "spec.yaml"
    )
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text(
        yaml.safe_dump(
            {
                "id": "FEAT-950",
                "title": "Separate docs root runtime smoke test",
                "type": "feature",
                "expected_commit_subject": "feat: test separate docs root runtime support",
                "planning_tier": "direct",
                "status": "backlog",
                "priority": "high",
                "objective": "Validate and run-all consume configured separate docs root.",
                "acceptance": ["Separate docs root is honored by runtime commands."],
                "artifacts": {},
            },
            sort_keys=False,
        ),
        encoding="utf-8",
    )

    validate_result = invoke_cli(["--project-root", str(tmp_path), "validate"])
    assert validate_result.exit_code == 0
    assert "spec validation: ok" in validate_result.stdout

    run_result = invoke_cli(
        ["--project-root", str(tmp_path), "run", "--all", "--dry-run"]
    )

    assert run_result.exit_code == 0
    assert "[dry-run] Resolved 1 feature file(s)." in run_result.stdout
    assert "feature=FEAT-950" in run_result.stdout
    assert (
        "docs.engineeringagent/spec/features/FEAT-950-separate-docs-root/spec.yaml"
        in run_result.stdout
    )


def test_init_with_codex_backend_scaffolds_codex_profile_config(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify codex backend selection scaffolds .codex/config.toml."""
    patch_non_tty(monkeypatch)
    monkeypatch.setattr(cli_init_module, "list_backends", lambda: ("codex", "opencode"))
    monkeypatch.setattr(cli_init_module, "default_backend_id", lambda: "opencode")

    result = invoke_cli(
        init_args(tmp_path, "slim", "--backend", "codex", *DEFAULT_LAUNCHER_ARGS)
    )

    assert result.exit_code == 0
    parsed_toml = tomllib.loads(
        (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    )
    assert parsed_toml["agents"]["backend"] == "codex"
    assert parsed_toml["agents"]["codex"]["profile"] == "engineeringagent"
    assert "model" not in parsed_toml["agents"]["codex"]

    codex_config = tmp_path / ".codex" / "config.toml"
    assert codex_config.exists()
    codex_config_text = codex_config.read_text(encoding="utf-8")
    assert "[profiles.engineeringagent]" in codex_config_text
    assert 'model = "gpt-5.3-codex"' in codex_config_text
    assert 'approval_policy = "never"' in codex_config_text
    assert not (tmp_path / ".opencode").exists()


@pytest.mark.parametrize(
    ("prompt_input", "expected_profile"),
    [("keep", "custom"), ("overwrite", "engineeringagent")],
)
def test_init_with_codex_backend_profile_conflict_prompts_for_keep_or_overwrite(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    prompt_input: str,
    expected_profile: str,
) -> None:
    """Verify interactive codex profile conflict handling keeps or overwrites as selected."""
    patch_tty(monkeypatch, backends=("codex", "opencode"), default_backend="opencode")
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "codex"\n\n[agents.codex]\nprofile = "custom"\n',
        encoding="utf-8",
    )
    prompts: list[str] = []

    def _fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return prompt_input

    monkeypatch.setattr("builtins.input", _fake_input)
    result = invoke_cli(
        init_args(tmp_path, "slim", "--backend", "codex", *DEFAULT_LAUNCHER_ARGS)
    )

    assert result.exit_code == 0
    assert prompts
    assert any("keep/overwrite" in prompt.lower() for prompt in prompts)
    persisted = tomllib.loads(
        (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    )
    assert persisted["agents"]["backend"] == "codex"
    assert persisted["agents"]["codex"]["profile"] == expected_profile


def test_init_with_codex_backend_profile_conflict_invalid_input_fails_and_preserves(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid interactive codex-profile input fails before any scaffold mutation."""
    patch_tty(monkeypatch, backends=("codex", "opencode"), default_backend="opencode")
    config_path = tmp_path / "engineeringagent.toml"
    config_path.write_text(
        '[agents]\nbackend = "codex"\n\n[agents.codex]\nprofile = "custom"\n',
        encoding="utf-8",
    )
    monkeypatch.setattr("builtins.input", lambda _prompt: "invalid")

    result = invoke_cli(
        init_args(tmp_path, "slim", "--backend", "codex", *DEFAULT_LAUNCHER_ARGS)
    )

    assert result.exit_code == 1
    assert "codex profile handling must be 'keep' or 'overwrite'" in result.stdout
    persisted = tomllib.loads(config_path.read_text(encoding="utf-8"))
    assert persisted["agents"]["codex"]["profile"] == "custom"
    assert not (tmp_path / "AGENTS.md").exists()
    assert not (tmp_path / "docs" / "spec").exists()
    assert not (tmp_path / ".codex" / "config.toml").exists()


def test_init_with_codex_backend_profile_conflict_non_interactive_keeps_existing(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify non-interactive init preserves an existing conflicting codex profile."""
    patch_non_tty(monkeypatch)
    monkeypatch.setattr(cli_init_module, "list_backends", lambda: ("codex", "opencode"))
    monkeypatch.setattr(cli_init_module, "default_backend_id", lambda: "opencode")
    fail_on_input(monkeypatch)
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "codex"\n\n[agents.codex]\nprofile = "custom"\n',
        encoding="utf-8",
    )

    result = invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--backend",
            "codex",
            "--no-precommit-install",
        ]
    )

    assert result.exit_code == 0
    persisted = tomllib.loads(
        (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    )
    assert persisted["agents"]["backend"] == "codex"
    assert persisted["agents"]["codex"]["profile"] == "custom"


def test_init_appends_backend_to_existing_engineeringagent_toml(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init appends [agents].backend when config exists without it."""
    monkeypatch.setattr(
        cli_init_module, "list_backends", lambda: ("opencode", "mock-b")
    )
    monkeypatch.setattr(cli_init_module, "default_backend_id", lambda: "opencode")
    patch_non_tty(monkeypatch)

    config_path = tmp_path / "engineeringagent.toml"
    config_path.write_text('docs-root = "docs.engineeringagent"\n', encoding="utf-8")
    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    assert load_engineeringagent_config(tmp_path) == {
        "docs-root": "docs.engineeringagent",
        "agents": {"backend": "opencode"},
    }


def test_init_preserves_existing_backend_without_force(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init does not overwrite existing backend unless --force is used."""
    monkeypatch.setattr(
        cli_init_module, "list_backends", lambda: ("opencode", "mock-b")
    )
    monkeypatch.setattr(cli_init_module, "default_backend_id", lambda: "opencode")
    patch_non_tty(monkeypatch)

    config_path = tmp_path / "engineeringagent.toml"
    config_path.write_text('[agents]\nbackend = "mock-b"\n', encoding="utf-8")
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

    assert result.exit_code == 0
    assert load_engineeringagent_config(tmp_path) == {"agents": {"backend": "mock-b"}}
