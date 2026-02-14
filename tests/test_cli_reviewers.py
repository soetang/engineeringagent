from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from typing import Any

import yaml

from engineeringagent import cli as cli_module
from engineeringagent.cli import build_parser
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
    prompt_path.write_text("Review code quality.\n", encoding="utf-8")


def test_reviewers_subcommands_registered() -> None:
    parser = build_parser()

    list_args = parser.parse_args(["reviewers", "list"])
    plan_args = parser.parse_args(
        ["reviewers", "plan", "--profile", "loop_fast", "--phase", "iteration_end"]
    )
    run_args = parser.parse_args(
        [
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
    init_args = parser.parse_args(["reviewers", "init"])

    assert list_args.command == "reviewers"
    assert list_args.reviewers_cmd == "list"
    assert callable(list_args.func)
    assert plan_args.reviewers_cmd == "plan"
    assert run_args.reviewers_cmd == "run"
    assert init_args.reviewers_cmd == "init"


def test_reviewers_list_prints_profile_names(tmp_path: Path, capsys: Any) -> None:
    _write_reviewers_config(tmp_path)
    parser = build_parser()

    args = parser.parse_args(["--project-root", str(tmp_path), "reviewers", "list"])
    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert output.strip() == "loop_fast"


def test_reviewers_plan_prints_deterministic_json(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    _write_reviewers_config(tmp_path)
    parser = build_parser()
    monkeypatch.setattr(
        cli_module,
        "collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("src/engineeringagent/cli.py",),
            run_all=False,
            reason=None,
        ),
    )

    args = parser.parse_args(
        [
            "--project-root",
            str(tmp_path),
            "reviewers",
            "plan",
            "--profile",
            "loop_fast",
            "--phase",
            "iteration_end",
        ]
    )
    code = args.func(args)
    output = capsys.readouterr().out

    assert code == 0
    assert json.loads(output) == [
        {
            "decision": "run",
            "reason": "always_run_no_on_change",
            "reviewer": "code_simplifier",
        }
    ]


def test_reviewers_run_returns_decision_json(
    tmp_path: Path,
    capsys: Any,
    monkeypatch: Any,
) -> None:
    _write_reviewers_config(tmp_path)
    parser = build_parser()

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

    args = parser.parse_args(
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
    code = args.func(args)
    payload = json.loads(capsys.readouterr().out)

    assert code == 0
    assert payload == {
        "decision": "approve",
        "required_actions": [],
        "summary": "Looks good.",
    }
