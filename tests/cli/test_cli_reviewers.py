from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml
import pytest
from typer.testing import CliRunner

from engineeringagent import cli as cli_module
from engineeringagent.gates import ChangedPathsResult


def _write_reviewers_config(tmp_path: Path) -> None:
    reviewers_path = tmp_path / "harness" / "reviewers.yaml"
    reviewers_path.parent.mkdir(parents=True, exist_ok=True)
    reviewers_path.write_text(
        yaml.safe_dump(
            {
                "contract_version": "1.0",
                "profiles": {"loop_fast": ["code_simplifier"]},
                "reviewers": {
                    "code_simplifier": {
                        "prompt_file": "harness/reviewers/prompts/code_simplifier.md",
                        "trigger": {"phase": "iteration_end"},
                        "approval": {"mode": "advisory"},
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )
    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text(
        "$responseformat\n\nReview code quality.\n", encoding="utf-8"
    )


def _invoke_cli(args: list[str]) -> Any:
    runner = CliRunner(mix_stderr=False)
    return runner.invoke(cli_module.build_typer_app(), args)


def test_reviewers_subcommands_registered() -> None:
    result = _invoke_cli(["reviewers", "--help"])

    assert result.exit_code == 0
    for token in ("init", "list", "plan", "run"):
        assert token in result.stdout


def test_main_reviewers_list_uses_typer_handler(monkeypatch: Any) -> None:
    recorded: dict[str, object] = {}

    def _fake_cmd_reviewers_list(args: Any) -> int:
        recorded["project_root"] = args.project_root
        return 0

    monkeypatch.setattr(cli_module, "cmd_reviewers_list", _fake_cmd_reviewers_list)

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(["--project-root", "repo", "reviewers", "list"])

    assert exc_info.value.code == 0
    assert recorded == {"project_root": "repo"}


def test_reviewers_list_prints_profile_names(tmp_path: Path) -> None:
    _write_reviewers_config(tmp_path)
    result = _invoke_cli(["--project-root", str(tmp_path), "reviewers", "list"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "loop_fast"


def test_reviewers_plan_prints_deterministic_json(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _write_reviewers_config(tmp_path)
    monkeypatch.setattr(
        cli_module,
        "collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("src/engineeringagent/cli.py",),
            run_all=False,
            reason=None,
        ),
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "reviewers",
            "plan",
            "--profile",
            "loop_fast",
            "--phase",
            "feature_done",
        ]
    )

    assert result.exit_code == 0
    assert json.loads(result.stdout) == [
        {
            "decision": "run",
            "reason": "always_run_no_on_change",
            "reviewer": "code_simplifier",
        }
    ]


def test_reviewers_run_returns_decision_json(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    _write_reviewers_config(tmp_path)

    monkeypatch.setattr(
        cli_module,
        "collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("src/engineeringagent/reviewers.py",),
            run_all=False,
            reason=None,
        ),
    )
    monkeypatch.setattr(
        cli_module,
        "start_agent",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout='{"decision":"approve","summary":"Looks good."}',
            stderr="",
            returncode=0,
        ),
    )

    result = _invoke_cli(
        [
            "--project-root",
            str(tmp_path),
            "reviewers",
            "run",
            "--reviewer",
            "code_simplifier",
            "--feature-id",
            "FEAT-050",
            "--feature-path",
            "docs/spec/features/FEAT-050.yaml",
        ]
    )
    payload = json.loads(result.stdout)

    assert result.exit_code == 0
    assert payload == {
        "decision": "approve",
        "required_actions": [],
        "summary": "Looks good.",
    }


def test_reviewers_init_writes_baseline_files(tmp_path: Path) -> None:
    result = _invoke_cli(["--project-root", str(tmp_path), "reviewers", "init"])

    assert result.exit_code == 0
    assert result.stdout.strip() == "reviewers init complete: created=2 skipped=0"
    assert (tmp_path / "harness" / "reviewers.yaml").is_file()
    code_simplifier_prompt = (
        tmp_path / "harness" / "reviewers" / "prompts" / "code_simplifier.md"
    )
    assert code_simplifier_prompt.is_file()
    assert "$responseformat" in code_simplifier_prompt.read_text(encoding="utf-8")


def test_reviewers_init_skips_existing_files_without_force(
    tmp_path: Path,
) -> None:
    first_result = _invoke_cli(["--project-root", str(tmp_path), "reviewers", "init"])
    assert first_result.exit_code == 0

    second_result = _invoke_cli(["--project-root", str(tmp_path), "reviewers", "init"])

    assert second_result.exit_code == 0
    assert (
        second_result.stdout.strip() == "reviewers init complete: created=0 skipped=2"
    )
