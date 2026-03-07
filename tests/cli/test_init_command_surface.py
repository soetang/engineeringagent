from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from engineeringagent import cli as cli_module
from engineeringagent.cli import init as cli_init_module
from engineeringagent.init_service import InitDependencies, InitRequest
from tests.cli.init_command_support import (
    DEFAULT_LAUNCHER_ARGS,
    UV_RUN_TOKEN,
    UVX_TOKEN,
    fail_on_input,
    init_args,
    invoke_cli,
    patch_non_tty,
    patch_tty,
)


def test_scaffold_agents_bootstrap_template_uses_default_launcher_token() -> None:
    from engineeringagent.init_scaffold import build_scaffold_agents_markdown

    template_payload = build_scaffold_agents_markdown()

    assert UVX_TOKEN in template_payload
    assert UV_RUN_TOKEN not in template_payload


def test_init_subcommand_registered(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verify Typer routes the init command to the init handler."""
    recorded: dict[str, object] = {}

    def _fake_cmd_init(args: Any) -> int:
        recorded["project_root"] = args.project_root
        return 0

    monkeypatch.setattr(cli_module, "cmd_init", _fake_cmd_init)
    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert recorded == {"project_root": str(tmp_path)}


def test_cmd_init_accepts_explicit_cli_overrides(tmp_path: Path) -> None:
    (tmp_path / "AGENTS.md").write_text("existing agents\n", encoding="utf-8")
    observed = SimpleNamespace(
        request=None,
        deps=None,
    )

    def _list_backends() -> tuple[str, ...]:
        return ("alpha", "beta", "opencode")

    def _resolve_agents_backend_id(project_root: Path) -> str | None:
        assert project_root == tmp_path.resolve()
        return "beta"

    def _default_backend_id() -> str:
        return "alpha"

    def _resolve_docs_dir(
        project_root: Path,
        docs_mode: str | None,
        scaffold_docs_dir: str,
    ) -> tuple[str | None, str | None]:
        assert project_root == tmp_path.resolve()
        assert docs_mode == "separate"
        assert scaffold_docs_dir == "docs.custom"
        return "docs.override", None

    def _fake_run_init_command(request: InitRequest, deps: InitDependencies) -> int:
        observed.request = request
        observed.deps = deps
        return 0

    adapters = cli_init_module.InitCliAdapters(
        backend=cli_init_module.InitCliBackendAdapters(
            list_backends_fn=_list_backends,
            resolve_agents_backend_id_fn=_resolve_agents_backend_id,
            default_backend_id_fn=_default_backend_id,
        ),
        command=cli_init_module.InitCliCommandAdapters(
            run_init_command_fn=_fake_run_init_command
        ),
        selection=cli_init_module.InitCliSelectionAdapters(
            resolve_docs_dir_fn=_resolve_docs_dir
        ),
    )

    result = cli_init_module.cmd_init(
        SimpleNamespace(
            project_root=str(tmp_path),
            force=True,
            scaffold_profile="python_uv",
            docs_mode="separate",
            scaffold_docs_dir="docs.custom",
            agents_mode="overwrite",
            pack="slim",
            backend="opencode",
            agents_launcher="uvx",
            model="openai/gpt-5.3-codex",
            no_precommit_install=True,
        ),
        adapters=adapters,
    )

    assert result == 0
    request = observed.request
    assert request is not None
    assert request.project_root == tmp_path.resolve()
    assert request.force is True
    assert request.scaffold_profile == "python_uv"
    assert request.docs_mode == "separate"
    assert request.scaffold_docs_dir == "docs.custom"
    assert request.pack == "slim"
    assert request.backend == "opencode"
    assert request.agents_mode == "overwrite"
    assert request.agents_launcher == "uvx"
    assert request.model == "openai/gpt-5.3-codex"
    assert request.no_precommit_install is True
    deps = observed.deps
    assert deps is not None
    assert (
        deps.resolve_backend(
            project_root=request.project_root,
            backend=request.backend,
            force=request.force,
        )
        == ("opencode", None)
    )
    assert (
        deps.resolve_docs_dir(
            project_root=request.project_root,
            docs_mode=request.docs_mode,
            scaffold_docs_dir=request.scaffold_docs_dir,
        )
        == ("docs.override", None)
    )
    assert (
        deps.resolve_agents_mode(
            project_root=request.project_root,
            agents_mode=request.agents_mode,
        )
        == ("overwrite", None)
    )
    assert (
        deps.resolve_agents_launcher(agents_launcher=request.agents_launcher)
        == ("uvx", None)
    )


def test_init_help_documents_model_option() -> None:
    """Verify init help keeps --model docs backend-agnostic."""
    result = invoke_cli(["init", "--help"])

    assert result.exit_code == 0
    assert "--model" in result.stdout
    assert "openai/gpt-5.3-codex" in result.stdout
    assert "OpenCode" not in result.stdout
    assert ".opencode/" not in result.stdout


def test_init_model_flag_controls_scaffolded_opencode_agent(tmp_path: Path) -> None:
    """Verify --model pins the scaffolded OpenCode agent model."""
    result = invoke_cli(
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
    payload = (
        tmp_path / ".opencode" / "agents" / "engineeringagent.md"
    ).read_text(encoding="utf-8")
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
    patch_non_tty(monkeypatch)
    fail_on_input(monkeypatch)

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "pack=slim" in result.stdout


def test_init_prompts_for_pack_when_omitted_and_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init prompts for pack selection when omitted in a TTY."""
    patch_tty(monkeypatch)
    answers = iter(("standard", ""))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

    assert result.exit_code == 0
    assert "pack=standard" in result.stdout


def test_init_pack_arg_never_prompts_even_on_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify providing the pack positional disables the interactive prompt."""
    patch_tty(monkeypatch)
    fail_on_input(monkeypatch)

    result = invoke_cli(init_args(tmp_path, "slim", "--agents-launcher", "uvx"))

    assert result.exit_code == 0
    assert "pack=slim" in result.stdout


def test_init_prompts_for_agents_launcher_when_omitted_and_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify init prompts for AGENTS launcher wording when AGENTS will be written."""
    patch_tty(monkeypatch)
    prompts: list[str] = []

    def _fake_input(prompt: str) -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", _fake_input)
    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "slim", "--no-precommit-install"]
    )

    assert result.exit_code == 0
    assert len(prompts) == 1
    assert "AGENTS launcher" in prompts[0]
    assert "uvx" in prompts[0]
    assert "uv-run" in prompts[0]
    assert "engineeringagent" in prompts[0]


def test_init_agents_launcher_option_skips_prompt_even_on_tty(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify explicit --agents-launcher disables interactive launcher prompt."""
    patch_tty(monkeypatch)
    fail_on_input(monkeypatch)

    result = invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--agents-launcher",
            "uv-run",
            "--no-precommit-install",
        ]
    )

    assert result.exit_code == 0
    assert "agents_launcher=uv-run" in result.stdout
    rendered_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert UV_RUN_TOKEN in rendered_agents
    assert UVX_TOKEN not in rendered_agents


def test_init_agents_launcher_prompt_invalid_input_returns_deterministic_error(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify invalid launcher prompt input exits before any scaffold mutation."""
    patch_tty(monkeypatch)
    answers = iter(("overwrite", "invalid"))
    monkeypatch.setattr("builtins.input", lambda _prompt: next(answers))
    agents_path = tmp_path / "AGENTS.md"
    original_agents = "# User guidance\n"
    agents_path.write_text(original_agents, encoding="utf-8")

    result = invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--no-precommit-install",
        ]
    )

    assert result.exit_code == 1
    assert (
        "init input error: AGENTS launcher must be one of: "
        "uvx, uv-run, engineeringagent"
    ) in result.stdout
    assert agents_path.read_text(encoding="utf-8") == original_agents
    assert not (tmp_path / "AGENTS.user.md").exists()
    assert not (tmp_path / "AGENTS.user.2.md").exists()
    assert not (tmp_path / "docs" / "spec").exists()
    assert not (tmp_path / "engineeringagent.toml").exists()
    assert not (tmp_path / ".opencode").exists()
    assert not (tmp_path / ".codex" / "config.toml").exists()


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


def test_init_writes_precommit_and_empty_gate_profiles(tmp_path: Path) -> None:
    """Verify init writes pre-commit wiring and harness/checks.yaml."""
    import yaml

    result = invoke_cli(["--project-root", str(tmp_path), "init"])

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


def test_init_defaults_to_core_language_agnostic_profile(tmp_path: Path) -> None:
    """Verify init defaults to the language-agnostic core scaffold profile."""
    result = invoke_cli(["--project-root", str(tmp_path), "init"])

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
    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "--scaffold-profile", "python_uv"]
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
    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "--scaffold-profile", "python_uv"]
    )

    assert result.exit_code == 0
    commit_msg_script_text = (
        tmp_path / "harness" / "fitness-functions" / "validate_commit_messages.py"
    ).read_text(encoding="utf-8")
    assert "import subprocess" not in commit_msg_script_text
    assert "subprocess." not in commit_msg_script_text
    assert not (tmp_path / "harness" / "gates.yaml").exists()


def test_python_uv_commit_msg_validator_builds_pattern_from_allowed_types(
    tmp_path: Path,
) -> None:
    """Verify scaffolded commit-msg validator keeps types/regex in sync."""
    result = invoke_cli(
        ["--project-root", str(tmp_path), "init", "--scaffold-profile", "python_uv"]
    )

    assert result.exit_code == 0
    commit_msg_script_text = (
        tmp_path / "harness" / "fitness-functions" / "validate_commit_messages.py"
    ).read_text(encoding="utf-8")
    assert "ALLOWED_COMMIT_TYPES" in commit_msg_script_text
    assert "_ALLOWED_TYPES_PATTERN" in commit_msg_script_text
    assert "re.escape" in commit_msg_script_text
    assert "COMMIT_SUBJECT_PATTERN" in commit_msg_script_text
    assert "(feat|fix|spec|docs|chore|test)" not in commit_msg_script_text


def test_init_renders_scaffold_from_template_files(tmp_path: Path) -> None:
    """Verify init materializes the expected scaffold files with launcher substitution."""
    result = invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "init",
            "slim",
            "--backend",
            "opencode",
            "--model",
            "openai/gpt-5.3-codex-spark",
            "--no-precommit-install",
        ]
    )

    assert result.exit_code == 0
    assert (tmp_path / ".pre-commit-config.yaml").exists()
    rendered_agents = (tmp_path / "AGENTS.md").read_text(encoding="utf-8")
    assert UVX_TOKEN in rendered_agents
    assert UV_RUN_TOKEN not in rendered_agents
    backend_agent = (
        tmp_path / ".opencode" / "agents" / "engineeringagent.md"
    ).read_text(encoding="utf-8")
    assert "openai/gpt-5.3-codex-spark" in backend_agent
    assert (tmp_path / ".opencode" / "agents" / "engineeringagent.md").exists()
    assert (tmp_path / ".opencode" / ".gitignore").exists()


def test_init_template_rendering_is_deterministic() -> None:
    """Verify scaffold template rendering is deterministic across repeated calls."""
    from engineeringagent.init_scaffold import build_baseline_scaffold_manifest

    first = build_baseline_scaffold_manifest(
        docs_dir="docs.engineeringagent",
        profile="python_uv",
    )
    second = build_baseline_scaffold_manifest(
        docs_dir="docs.engineeringagent",
        profile="python_uv",
    )

    assert first == second
