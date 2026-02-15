from __future__ import annotations

import json
import subprocess
import sys
from argparse import Namespace
from pathlib import Path
from typing import Any

import pytest
import yaml

from engineeringagent import cli as cli_module
from engineeringagent.cli import cmd_gates_plan, cmd_gates_run
from engineeringagent.gates import (
    ALWAYS_RUN_NO_ON_CHANGE_REASON,
    ChangedPathsResult,
    FALLBACK_CHANGE_DISCOVERY_REASON,
    MATCHED_ON_CHANGE_REASON,
    NO_ON_CHANGE_MATCH_REASON,
    collect_changed_paths,
    list_profiles,
    load_gate_config,
    normalize_gate_runner,
    plan_profile,
    run_profile,
)
from engineeringagent.on_change_matcher import path_matches_any_glob


def test_load_gate_config_scaffolds_missing_gates_file(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"

    config = load_gate_config(gates_path)

    assert gates_path.exists()
    assert list_profiles(config) == ["loop_fast", "precommit"]


def test_scaffolded_gates_config_has_expected_commands(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"

    load_gate_config(gates_path)
    config = yaml.safe_load(gates_path.read_text(encoding="utf-8"))

    assert (
        config["gates"]["ruff_validate"]["run"]
        == "uv run ruff check src/engineeringagent"
    )
    assert (
        config["gates"]["pyright_validate"]["run"]
        == "uv run pyright src/engineeringagent tests harness"
    )
    assert config["gates"]["pytest_validate"]["run"] == "uv run pytest -q"
    assert config["gates"]["spec_validate"]["on_change"] == [
        "docs/spec/**/*.yaml",
        "docs/spec/**/*.yml",
        "docs/spec/**/*.json",
    ]
    assert config["gates"]["pyright_validate"]["on_change"] == [
        "src/**/*.py",
        "tests/**/*.py",
        "harness/**/*.py",
    ]
    assert config["gates"]["pytest_validate"]["on_change"] == [
        "src/**/*.py",
        "tests/**/*.py",
        "harness/**/*.py",
    ]
    assert config["profiles"]["precommit"] == [
        "yaml_validate",
        "spec_validate",
        "fitness_validate",
        "mdformat_validate",
        "ruff_validate",
        "pyright_validate",
        "pytest_validate",
    ]
    assert (
        config["gates"]["fitness_validate"]["run"]
        == "uv run python -m engineeringagent.cli fitness run --format json"
    )
    assert (
        config["gates"]["yaml_validate"]["run"]
        == "uv run python harness/fitness-functions/validate_yaml.py"
    )
    assert (
        config["gates"]["opencode_permission_probe"]["run"]
        == "uv run python harness/fitness-functions/permission_probe.py"
    )
    assert "precommit" in config["profiles"]
    assert "loop_fast" in config["profiles"]
    assert "opencode_permission_probe" not in config["profiles"]["loop_fast"]


def test_default_loop_fast_profile_excludes_permission_probe() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config = load_gate_config(repo_root / "harness" / "gates.yaml")

    assert "opencode_permission_probe" not in config["profiles"]["loop_fast"]


def test_repo_default_gates_support_spec_only_planning() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config = load_gate_config(repo_root / "harness" / "gates.yaml")

    decisions = plan_profile(
        config,
        "precommit",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    decision_by_gate = {entry["gate"]: entry for entry in decisions}
    assert decision_by_gate["yaml_validate"]["decision"] == "run"
    assert decision_by_gate["spec_validate"]["decision"] == "run"
    assert decision_by_gate["pyright_validate"]["decision"] == "skip"
    assert decision_by_gate["pytest_validate"]["decision"] == "skip"


def test_repo_default_gates_run_heavy_code_checks_for_python_changes() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config = load_gate_config(repo_root / "harness" / "gates.yaml")

    decisions = plan_profile(
        config,
        "precommit",
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/gates.py",),
            run_all=False,
            reason=None,
        ),
    )

    decision_by_gate = {entry["gate"]: entry for entry in decisions}
    assert decision_by_gate["pyright_validate"]["decision"] == "run"
    assert decision_by_gate["pytest_validate"]["decision"] == "run"


def test_list_profiles_returns_empty_when_profiles_is_not_mapping() -> None:
    assert list_profiles({"profiles": ["not", "a", "mapping"]}) == []


def test_run_profile_rejects_unknown_profile(tmp_path: Path) -> None:
    with pytest.raises(ValueError, match="unknown profile: loop_fast"):
        run_profile(
            config={"profiles": {}, "gates": {}}, profile="loop_fast", cwd=tmp_path
        )


def test_run_profile_rejects_gate_without_run_command(tmp_path: Path) -> None:
    config = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {"spec_validate": {}},
    }

    with pytest.raises(ValueError, match="gate 'spec_validate' has no run command"):
        run_profile(config=config, profile="loop_fast", cwd=tmp_path)


def test_empty_profile_returns_friendly_success_message(
    tmp_path: Path, capsys: Any
) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {
                    "precommit": [],
                },
                "gates": {},
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    code = cmd_gates_run(Namespace(project_root=str(tmp_path), profile="precommit"))
    output = capsys.readouterr().out

    assert code == 0
    assert "gates profile has no configured gates: precommit" in output


def test_load_gate_config_rejects_invalid_contract(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {
                    "precommit": ["yaml_validate"],
                },
                "gates": {
                    "yaml_validate": {
                        "run": 123,
                        "extra": True,
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        load_gate_config(gates_path)

    message = str(excinfo.value)
    assert "invalid gates config" in message
    assert "gates.yaml:gates.yaml_validate.extra" in message
    assert "gates.yaml:gates.yaml_validate.run" in message


def test_load_gate_config_accepts_on_change_selectors(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["spec_validate"]},
                "gates": {
                    "spec_validate": {
                        "run": "uv run python -m engineeringagent.cli validate",
                        "on_change": ["docs/spec/**/*.yaml", "docs/spec/**/*.json"],
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    config = load_gate_config(gates_path)

    assert config["gates"]["spec_validate"]["on_change"] == [
        "docs/spec/**/*.yaml",
        "docs/spec/**/*.json",
    ]


def test_load_gate_config_accepts_legacy_run_and_structured_command_runner(
    tmp_path: Path,
) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["legacy_gate", "structured_gate"]},
                "gates": {
                    "legacy_gate": {"run": "uv run pytest -q"},
                    "structured_gate": {
                        "runner": {
                            "type": "command",
                            "command": "uv run ruff check src/engineeringagent",
                        }
                    },
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    config = load_gate_config(gates_path)

    assert config["gates"]["legacy_gate"]["run"] == "uv run pytest -q"
    assert config["gates"]["structured_gate"]["runner"] == {
        "type": "command",
        "command": "uv run ruff check src/engineeringagent",
    }


def test_load_gate_config_rejects_gate_with_both_run_and_runner(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["spec_validate"]},
                "gates": {
                    "spec_validate": {
                        "run": "uv run pytest -q",
                        "runner": {"type": "command", "command": "uv run pytest -q"},
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="define exactly one of run or runner"):
        load_gate_config(gates_path)


def test_load_gate_config_rejects_gate_with_neither_run_nor_runner(
    tmp_path: Path,
) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["spec_validate"]},
                "gates": {"spec_validate": {"on_change": ["src/**/*.py"]}},
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match="define exactly one of run or runner"):
        load_gate_config(gates_path)


def test_load_gate_config_rejects_unknown_gate_fields(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["spec_validate"]},
                "gates": {
                    "spec_validate": {
                        "run": "uv run pytest -q",
                        "unknown": True,
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        load_gate_config(gates_path)

    assert "gates.yaml:gates.spec_validate.unknown" in str(excinfo.value)


def test_load_gate_config_defaults_missing_contract_version_to_v1(
    tmp_path: Path,
) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["spec_validate"]},
                "gates": {"spec_validate": {"run": "uv run pytest -q"}},
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    config = load_gate_config(gates_path)

    assert config["contract_version"] == "1.0"


def test_normalize_gate_runner_maps_legacy_run_to_command_runner() -> None:
    runner = normalize_gate_runner({"run": "uv run pytest -q"})

    assert runner == {"type": "command", "command": "uv run pytest -q"}


def test_load_gate_config_rejects_invalid_on_change_selectors(tmp_path: Path) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["spec_validate"]},
                "gates": {
                    "spec_validate": {
                        "run": "uv run pytest -q",
                        "on_change": [],
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    with pytest.raises(ValueError) as excinfo:
        load_gate_config(gates_path)

    assert "gates.yaml:gates.spec_validate.on_change" in str(excinfo.value)


def test_collect_changed_paths_supports_base_and_head(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_subprocess_run(
        command: Any,
        **kwargs: Any,
    ) -> Any:
        captured["command"] = command
        captured["kwargs"] = kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout="M\tdocs/spec/features/FEAT-049.yaml\n",
            stderr="",
        )

    monkeypatch.setattr("engineeringagent.gates.subprocess.run", fake_subprocess_run)

    result = collect_changed_paths(tmp_path, base="origin/main", head="HEAD")

    assert captured["command"] == [
        "git",
        "diff",
        "--name-status",
        "--find-renames",
        "--diff-filter=AMDR",
        "origin/main",
        "HEAD",
    ]
    assert captured["kwargs"]["cwd"] == tmp_path
    assert result.run_all is False
    assert result.reason is None
    assert result.paths == ("docs/spec/features/FEAT-049.yaml",)


def test_collect_changed_paths_includes_rename_old_and_new(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    def fake_subprocess_run(command: Any, **kwargs: Any) -> Any:
        del kwargs
        return subprocess.CompletedProcess(
            command,
            0,
            stdout=(
                "R100\tdocs/spec/features/old-name.yaml\t"
                "docs/spec/features/new-name.yaml\n"
            ),
            stderr="",
        )

    monkeypatch.setattr("engineeringagent.gates.subprocess.run", fake_subprocess_run)

    result = collect_changed_paths(tmp_path)

    assert result.run_all is False
    assert result.reason is None
    assert result.paths == (
        "docs/spec/features/new-name.yaml",
        "docs/spec/features/old-name.yaml",
    )


def test_collect_changed_paths_falls_back_to_run_all_when_diff_fails(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    def fake_subprocess_run(command: Any, **kwargs: Any) -> Any:
        del kwargs
        return subprocess.CompletedProcess(
            command,
            1,
            stdout="",
            stderr="fatal: ambiguous argument 'missing-ref': unknown revision",
        )

    monkeypatch.setattr("engineeringagent.gates.subprocess.run", fake_subprocess_run)

    result = collect_changed_paths(tmp_path, base="missing-ref", head="HEAD")

    assert result.paths == ()
    assert result.run_all is True
    assert result.reason == FALLBACK_CHANGE_DISCOVERY_REASON


def test_path_matches_any_glob_matches_nested_path() -> None:
    assert path_matches_any_glob(
        "src/engineeringagent/gates.py",
        ["src/**/*.py"],
    )


def test_path_matches_any_glob_normalizes_mixed_path_separators() -> None:
    assert path_matches_any_glob(
        r"src\engineeringagent\gates.py",
        ["src/**/*.py"],
    )


def test_path_matches_any_glob_returns_false_when_no_pattern_matches() -> None:
    assert not path_matches_any_glob(
        "docs/spec/features/FEAT-056.yaml",
        ["src/**/*.py", "tests/**/*.py"],
    )


def test_plan_profile_emits_gate_decision_reason_envelope() -> None:
    config = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {
            "spec_validate": {
                "run": "uv run pytest -q",
                "on_change": ["docs/spec/**/*.yaml"],
            }
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert result == [
        {
            "gate": "spec_validate",
            "decision": "run",
            "reason": MATCHED_ON_CHANGE_REASON,
        }
    ]


def test_plan_profile_runs_when_on_change_matches_any_path() -> None:
    config = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {
            "spec_validate": {
                "run": "uv run pytest -q",
                "on_change": ["docs/spec/**/*.yaml", "src/**/*.py"],
            }
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert result[0]["decision"] == "run"


def test_plan_profile_skips_when_on_change_does_not_match() -> None:
    config = {
        "profiles": {"loop_fast": ["pyright_validate"]},
        "gates": {
            "pyright_validate": {
                "run": "uv run pyright src/engineeringagent tests",
                "on_change": ["src/**/*.py", "tests/**/*.py"],
            }
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert result[0]["decision"] == "skip"


def test_plan_profile_skips_when_changed_paths_are_empty() -> None:
    config = {
        "profiles": {"loop_fast": ["pytest_validate"]},
        "gates": {
            "pytest_validate": {
                "run": "uv run pytest -q",
                "on_change": ["src/**/*.py", "tests/**/*.py"],
            }
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
    )

    assert result[0]["decision"] == "skip"
    assert result[0]["reason"] == NO_ON_CHANGE_MATCH_REASON


def test_plan_profile_runs_when_rename_paths_include_match() -> None:
    config = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {
            "spec_validate": {
                "run": "uv run python -m engineeringagent.cli validate",
                "on_change": ["docs/spec/features/old-name.yaml"],
            }
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=(
                "docs/spec/features/new-name.yaml",
                "docs/spec/features/old-name.yaml",
            ),
            run_all=False,
            reason=None,
        ),
    )

    assert result[0]["decision"] == "run"
    assert result[0]["reason"] == MATCHED_ON_CHANGE_REASON


def test_plan_profile_runs_when_on_change_is_omitted() -> None:
    config = {
        "profiles": {"loop_fast": ["yaml_validate"]},
        "gates": {
            "yaml_validate": {
                "run": "uv run python harness/fitness-functions/validate_yaml.py"
            },
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert result[0]["decision"] == "run"


def test_plan_profile_reason_always_run_no_on_change() -> None:
    config = {
        "profiles": {"loop_fast": ["yaml_validate"]},
        "gates": {
            "yaml_validate": {
                "run": "uv run python harness/fitness-functions/validate_yaml.py"
            },
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/gates.py",), run_all=False, reason=None
        ),
    )

    assert result[0]["reason"] == ALWAYS_RUN_NO_ON_CHANGE_REASON


def test_plan_profile_reason_matched_on_change() -> None:
    config = {
        "profiles": {"loop_fast": ["spec_validate"]},
        "gates": {
            "spec_validate": {
                "run": "uv run python -m engineeringagent.cli validate",
                "on_change": ["docs/spec/**/*.yaml"],
            },
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert result[0]["reason"] == MATCHED_ON_CHANGE_REASON


def test_plan_profile_reason_no_on_change_match() -> None:
    config = {
        "profiles": {"loop_fast": ["pytest_validate"]},
        "gates": {
            "pytest_validate": {
                "run": "uv run pytest -q",
                "on_change": ["src/**/*.py", "tests/**/*.py"],
            }
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert result[0]["reason"] == NO_ON_CHANGE_MATCH_REASON


def test_plan_profile_reason_fallback_run_all_change_discovery_failed() -> None:
    config = {
        "profiles": {"loop_fast": ["spec_validate", "pytest_validate"]},
        "gates": {
            "spec_validate": {
                "run": "uv run python -m engineeringagent.cli validate",
                "on_change": ["docs/spec/**/*.yaml"],
            },
            "pytest_validate": {
                "run": "uv run pytest -q",
                "on_change": ["src/**/*.py", "tests/**/*.py"],
            },
        },
    }

    result = plan_profile(
        config,
        "loop_fast",
        changed_paths=ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=FALLBACK_CHANGE_DISCOVERY_REASON,
        ),
    )

    assert result == [
        {
            "gate": "spec_validate",
            "decision": "run",
            "reason": FALLBACK_CHANGE_DISCOVERY_REASON,
        },
        {
            "gate": "pytest_validate",
            "decision": "run",
            "reason": FALLBACK_CHANGE_DISCOVERY_REASON,
        },
    ]


def test_commit_msg_hook_configuration() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config_text = (repo_root / ".pre-commit-config.yaml").read_text(encoding="utf-8")

    assert "engineeringagent-commit-msg" in config_text
    assert (
        "harness/fitness-functions/validate_commit_messages.py --commit-msg-file"
        in config_text
    )
    assert "stages: [commit-msg]" in config_text


def test_commit_message_ci_gate_registered() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    workflow_text = (repo_root / ".github" / "workflows" / "ci.yaml").read_text(
        encoding="utf-8"
    )

    assert "Validate commit subjects" in workflow_text
    assert (
        "harness/fitness-functions/validate_commit_messages.py --commit-range"
        in workflow_text
    )


def test_run_profile_returns_failed_gate_output_for_loop_mode(tmp_path: Path) -> None:
    fail_stdout = "SPEC_VALIDATE_STDOUT_TOKEN"
    fail_stderr = "SPEC_VALIDATE_STDERR_TOKEN"
    config = {
        "profiles": {"loop_fast": ["pass_gate", "spec_validate", "after_fail"]},
        "gates": {
            "pass_gate": {"run": f'"{sys.executable}" -c "print(\'PASS_GATE\')"'},
            "spec_validate": {
                "run": (
                    f'"{sys.executable}" -c "import sys; '
                    f"print({fail_stdout!r}); print({fail_stderr!r}, file=sys.stderr); "
                    'sys.exit(1)"'
                )
            },
            "after_fail": {"run": f'"{sys.executable}" -c "print(\'SHOULD_NOT_RUN\')"'},
        },
    }

    ok, failed_gate, output = run_profile(
        config=config,
        profile="loop_fast",
        cwd=tmp_path,
        capture_output=True,
    )

    assert not ok
    assert failed_gate == "spec_validate"
    assert "[gate:pass_gate]" in output
    assert "[gate:spec_validate]" in output
    assert fail_stdout in output
    assert fail_stderr in output
    assert "SHOULD_NOT_RUN" not in output


def test_run_profile_reports_pyright_gate_failure(tmp_path: Path) -> None:
    pyright_stdout = "PYRIGHT_STDOUT_TOKEN"
    pyright_stderr = "PYRIGHT_STDERR_TOKEN"
    config = {
        "profiles": {"precommit": ["pyright_validate", "after_fail"]},
        "gates": {
            "pyright_validate": {
                "run": (
                    f'"{sys.executable}" -c "import sys; '
                    f"print({pyright_stdout!r}); "
                    f"print({pyright_stderr!r}, file=sys.stderr); "
                    'sys.exit(1)"'
                )
            },
            "after_fail": {"run": f'"{sys.executable}" -c "print(\'SHOULD_NOT_RUN\')"'},
        },
    }

    ok, failed_gate, output = run_profile(
        config=config,
        profile="precommit",
        cwd=tmp_path,
        capture_output=True,
    )

    assert not ok
    assert failed_gate == "pyright_validate"
    assert "[gate:pyright_validate]" in output
    assert pyright_stdout in output
    assert pyright_stderr in output
    assert "SHOULD_NOT_RUN" not in output


def test_run_profile_executes_only_planned_run_gates(tmp_path: Path) -> None:
    always_token = "ALWAYS_GATE_TOKEN"
    spec_token = "SPEC_GATE_TOKEN"
    skipped_token = "SKIPPED_GATE_TOKEN"
    config = {
        "profiles": {"loop_fast": ["always_gate", "spec_gate", "code_gate"]},
        "gates": {
            "always_gate": {
                "run": f'"{sys.executable}" -c "print({always_token!r})"',
            },
            "spec_gate": {
                "run": f'"{sys.executable}" -c "print({spec_token!r})"',
                "on_change": ["docs/spec/**/*.yaml"],
            },
            "code_gate": {
                "run": f'"{sys.executable}" -c "print({skipped_token!r})"',
                "on_change": ["src/**/*.py"],
            },
        },
    }

    ok, failed_gate, output = run_profile(
        config=config,
        profile="loop_fast",
        cwd=tmp_path,
        capture_output=True,
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert ok
    assert failed_gate is None
    assert always_token in output
    assert spec_token in output
    assert skipped_token not in output
    assert "[gate:always_gate]" in output
    assert "[gate:spec_gate]" in output
    assert "[gate:code_gate]" not in output


def test_run_profile_preserves_fail_fast_for_selected_gates(tmp_path: Path) -> None:
    fail_stdout = "SELECTED_FAIL_STDOUT"
    fail_stderr = "SELECTED_FAIL_STDERR"
    skipped_token = "SKIPPED_SHOULD_NOT_RUN"
    after_fail_token = "AFTER_FAIL_SHOULD_NOT_RUN"
    config = {
        "profiles": {
            "loop_fast": ["skip_gate", "fail_gate", "after_selected_fail_gate"]
        },
        "gates": {
            "skip_gate": {
                "run": f'"{sys.executable}" -c "print({skipped_token!r})"',
                "on_change": ["src/**/*.py"],
            },
            "fail_gate": {
                "run": (
                    f'"{sys.executable}" -c "import sys; print({fail_stdout!r}); '
                    f'print({fail_stderr!r}, file=sys.stderr); sys.exit(1)"'
                ),
                "on_change": ["docs/spec/**/*.yaml"],
            },
            "after_selected_fail_gate": {
                "run": f'"{sys.executable}" -c "print({after_fail_token!r})"',
                "on_change": ["docs/spec/**/*.yaml"],
            },
        },
    }

    ok, failed_gate, output = run_profile(
        config=config,
        profile="loop_fast",
        cwd=tmp_path,
        capture_output=True,
        changed_paths=ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    assert not ok
    assert failed_gate == "fail_gate"
    assert "[gate:skip_gate]" not in output
    assert "[gate:fail_gate]" in output
    assert "[gate:after_selected_fail_gate]" not in output
    assert fail_stdout in output
    assert fail_stderr in output
    assert skipped_token not in output
    assert after_fail_token not in output


def test_cmd_gates_run_output_behavior_unchanged(tmp_path: Path, capfd: Any) -> None:
    output_token = "DIRECT_GATES_RUN_OUTPUT_TOKEN"
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["emit"]},
                "gates": {
                    "emit": {
                        "run": (f'"{sys.executable}" -c "print({output_token!r})"')
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    code = cmd_gates_run(Namespace(project_root=str(tmp_path), profile="loop_fast"))
    output = capfd.readouterr().out

    assert code == 0
    assert output_token in output
    assert "gates profile passed: loop_fast" in output


def test_main_uses_typer_gates_tree_without_legacy_forward(monkeypatch: Any) -> None:
    captured: dict[str, Any] = {}

    def _fake_cmd_gates_run(args: Namespace) -> int:
        captured["project_root"] = args.project_root
        captured["profile"] = args.profile
        captured["base"] = args.base
        captured["head"] = args.head
        captured["explain"] = args.explain
        return 7

    assert not hasattr(cli_module, "_run_legacy_cli_command")

    monkeypatch.setattr(cli_module, "cmd_gates_run", _fake_cmd_gates_run)

    with pytest.raises(SystemExit) as exc_info:
        cli_module.main(
            [
                "--project-root",
                "repo",
                "gates",
                "run",
                "--profile",
                "loop_fast",
                "--base",
                "origin/main",
                "--head",
                "HEAD",
                "--explain",
            ]
        )

    assert exc_info.value.code == 7
    assert captured == {
        "project_root": "repo",
        "profile": "loop_fast",
        "base": "origin/main",
        "head": "HEAD",
        "explain": True,
    }


def test_cmd_gates_plan_supports_base_and_head_inputs(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["spec_validate"]},
                "gates": {
                    "spec_validate": {
                        "run": "uv run python -m engineeringagent.cli validate",
                        "on_change": ["docs/spec/**/*.yaml"],
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_collect_changed_paths(
        cwd: Path,
        *,
        base: str | None = None,
        head: str | None = None,
    ) -> ChangedPathsResult:
        captured["cwd"] = cwd
        captured["base"] = base
        captured["head"] = head
        return ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        )

    monkeypatch.setattr(
        "engineeringagent.cli.collect_changed_paths",
        fake_collect_changed_paths,
    )

    code = cmd_gates_plan(
        Namespace(
            project_root=str(tmp_path),
            profile="loop_fast",
            base="origin/main",
            head="HEAD",
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    assert captured == {
        "cwd": tmp_path,
        "base": "origin/main",
        "head": "HEAD",
    }
    assert output


def test_cmd_gates_plan_outputs_deterministic_decisions(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["always_gate", "spec_gate", "code_gate"]},
                "gates": {
                    "always_gate": {
                        "run": "uv run python harness/fitness-functions/validate_yaml.py"
                    },
                    "spec_gate": {
                        "run": "uv run python -m engineeringagent.cli validate",
                        "on_change": ["docs/spec/**/*.yaml"],
                    },
                    "code_gate": {
                        "run": "uv run pytest -q",
                        "on_change": ["src/**/*.py"],
                    },
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "engineeringagent.cli.collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",), run_all=False, reason=None
        ),
    )

    code = cmd_gates_plan(
        Namespace(
            project_root=str(tmp_path),
            profile="loop_fast",
            base=None,
            head=None,
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    assert json.loads(output) == [
        {
            "decision": "run",
            "gate": "always_gate",
            "reason": ALWAYS_RUN_NO_ON_CHANGE_REASON,
        },
        {
            "decision": "run",
            "gate": "spec_gate",
            "reason": MATCHED_ON_CHANGE_REASON,
        },
        {
            "decision": "skip",
            "gate": "code_gate",
            "reason": NO_ON_CHANGE_MATCH_REASON,
        },
    ]


def test_cmd_gates_plan_outputs_decision_reason_enums(
    tmp_path: Path,
    monkeypatch: Any,
    capsys: Any,
) -> None:
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["spec_gate", "code_gate"]},
                "gates": {
                    "spec_gate": {
                        "run": "uv run python -m engineeringagent.cli validate",
                        "on_change": ["docs/spec/**/*.yaml"],
                    },
                    "code_gate": {
                        "run": "uv run pytest -q",
                        "on_change": ["src/**/*.py"],
                    },
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "engineeringagent.cli.collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=FALLBACK_CHANGE_DISCOVERY_REASON,
        ),
    )

    code = cmd_gates_plan(
        Namespace(
            project_root=str(tmp_path),
            profile="loop_fast",
            base=None,
            head=None,
        )
    )
    output = capsys.readouterr().out

    assert code == 0
    decisions = json.loads(output)
    assert decisions[0]["reason"] == FALLBACK_CHANGE_DISCOVERY_REASON
    assert decisions[1]["reason"] == FALLBACK_CHANGE_DISCOVERY_REASON


def test_cmd_gates_run_supports_base_head_and_explain_output(
    tmp_path: Path,
    monkeypatch: Any,
    capfd: Any,
) -> None:
    output_token = "RUN_WITH_EXPLAIN_TOKEN"
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["emit"]},
                "gates": {
                    "emit": {
                        "run": (f'"{sys.executable}" -c "print({output_token!r})"')
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    captured: dict[str, Any] = {}

    def fake_collect_changed_paths(
        cwd: Path,
        *,
        base: str | None = None,
        head: str | None = None,
    ) -> ChangedPathsResult:
        captured["cwd"] = cwd
        captured["base"] = base
        captured["head"] = head
        return ChangedPathsResult(paths=(), run_all=False, reason=None)

    monkeypatch.setattr(
        "engineeringagent.cli.collect_changed_paths",
        fake_collect_changed_paths,
    )

    code = cmd_gates_run(
        Namespace(
            project_root=str(tmp_path),
            profile="loop_fast",
            base="origin/main",
            head="HEAD",
            explain=True,
        )
    )
    output = capfd.readouterr().out

    assert code == 0
    assert captured == {
        "cwd": tmp_path,
        "base": "origin/main",
        "head": "HEAD",
    }
    assert '"gate": "emit"' in output
    assert output_token in output


def test_cmd_gates_run_explain_prints_planner_decisions_before_execution(
    tmp_path: Path,
    monkeypatch: Any,
    capfd: Any,
) -> None:
    output_token = "ORDER_CHECK_GATE_OUTPUT"
    gates_path = tmp_path / "harness" / "gates.yaml"
    gates_path.parent.mkdir(parents=True, exist_ok=True)
    gates_path.write_text(
        yaml.safe_dump(
            {
                "profiles": {"loop_fast": ["emit"]},
                "gates": {
                    "emit": {
                        "run": (f'"{sys.executable}" -c "print({output_token!r})"')
                    }
                },
            },
            sort_keys=False,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "engineeringagent.cli.collect_changed_paths",
        lambda *_args, **_kwargs: ChangedPathsResult(
            paths=("docs/spec/features/FEAT-049.yaml",),
            run_all=False,
            reason=None,
        ),
    )

    code = cmd_gates_run(
        Namespace(
            project_root=str(tmp_path),
            profile="loop_fast",
            base=None,
            head=None,
            explain=True,
        )
    )
    output = capfd.readouterr().out

    assert code == 0
    explain_index = output.index('"gate": "emit"')
    gate_output_index = output.index(output_token)
    assert explain_index < gate_output_index


def test_fitness_gate_integration() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    config = load_gate_config(repo_root / "harness" / "gates.yaml")

    assert "fitness_validate" in config["gates"]
    assert (
        config["gates"]["fitness_validate"]["run"]
        == "uv run python -m engineeringagent.cli fitness run --format json"
    )
    assert "fitness_validate" in config["profiles"]["loop_fast"]
