from __future__ import annotations

from pathlib import Path

import pytest


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def test_run_checks_defaults_to_commands_and_fitness(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(tmp_path, phase="iteration_end")
    assert result.ok
    assert "[check:smoke]" in result.output


def test_run_checks_group_order_is_deterministic(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from engineeringagent.checks.api import ChecksRunResult
    from engineeringagent.checks.api import run_checks as run_checks_impl

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    calls: list[str] = []

    def _commands(*_args: object, **_kwargs: object) -> tuple[bool, str | None, str]:
        calls.append("commands")
        return True, None, "commands-out"

    def _fitness(*_args: object, **_kwargs: object) -> tuple[bool, str | None, str]:
        calls.append("fitness")
        return True, None, "fitness-out"

    monkeypatch.setattr(
        "engineeringagent.checks.api._run_commands_group",
        _commands,
    )
    monkeypatch.setattr(
        "engineeringagent.checks.api._run_fitness_group",
        _fitness,
    )

    result = run_checks_impl(
        tmp_path,
        phase="iteration_end",
        checks=["fitness", "commands"],
    )
    assert isinstance(result, ChecksRunResult)
    assert result.ok
    assert calls == ["commands", "fitness"]
    assert result.output == "commands-out\nfitness-out"


def test_run_checks_check_id_filters_to_single_check(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  a:",
                "    type: command",
                '    command: "python -c \\"print(\'a\')\\""',
                "  b:",
                "    type: command",
                '    command: "python -c \\"print(\'b\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["commands"],
        check_id="b",
    )
    assert result.ok
    assert "[check:b]" in result.output
    assert "[check:a]" not in result.output


def test_run_checks_unknown_check_id_is_deterministic_failure(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["commands"],
        check_id="missing",
    )
    assert not result.ok
    assert result.failed_check_id == "missing"
    assert "unknown" in result.output


def test_run_checks_reviewers_requires_feature_path(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    with pytest.raises(ValueError, match="feature_path"):
        run_checks(tmp_path, phase="iteration_end", checks=["reviewers"])


def test_run_checks_invalid_group_is_a_value_error(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    with pytest.raises(ValueError, match="unknown checks groups"):
        run_checks(tmp_path, phase="iteration_end", checks=["nope"])


def test_run_checks_invalid_phase_is_a_value_error(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    with pytest.raises(ValueError, match="unknown phase"):
        run_checks(tmp_path, phase="not-a-phase", checks=[])


def test_run_checks_missing_checks_yaml_is_config_failure(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    result = run_checks(tmp_path, phase="iteration_end", checks=["commands"])
    assert not result.ok
    assert result.failed_group == "config"
    assert "missing harness/checks.yaml" in result.output


def test_run_checks_check_id_without_harness_doc_fails_deterministically(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks import run_checks

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["validate"],
        check_id="smoke",
    )
    assert not result.ok
    assert result.failed_group == "selection"
    assert result.failed_check_id == "smoke"


def test_run_checks_reviewers_returns_not_implemented_result(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks import run_checks

    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Please review. $responseformat\n", encoding="utf-8")

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )

    calls: list[tuple[Path, str]] = []

    class _Proc:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout
            self.stderr = ""

    def _start_agent(execution_root: Path, prompt: str, **_kwargs: object) -> _Proc:
        calls.append((execution_root, prompt))
        event = {
            "sessionID": "s1",
            "type": "text",
            "part": {
                "text": '{"decision":"approve","summary":"ok","required_actions":[]}'
            },
        }
        import json

        return _Proc(json.dumps(event, sort_keys=True) + "\n")

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        start_agent_fn=_start_agent,
    )
    assert result.ok
    assert result.failed_group is None
    assert "[reviewer:doc_review] decision=approve" in result.output
    assert len(calls) == 1


def test_run_checks_reviewers_request_changes_fails_deterministically(
    tmp_path: Path,
) -> None:
    from engineeringagent.checks import run_checks

    prompt_path = tmp_path / "harness" / "reviewers" / "prompts" / "doc_review.md"
    prompt_path.parent.mkdir(parents=True, exist_ok=True)
    prompt_path.write_text("Please review. $responseformat\n", encoding="utf-8")

    feature_path = tmp_path / "docs" / "spec" / "features" / "FEAT-001.yaml"
    feature_path.parent.mkdir(parents=True, exist_ok=True)
    feature_path.write_text("id: FEAT-001\n", encoding="utf-8")

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                "    prompt_file: harness/reviewers/prompts/doc_review.md",
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )

    class _Proc:
        def __init__(self, stdout: str) -> None:
            self.stdout = stdout
            self.stderr = ""

    def _start_agent(execution_root: Path, prompt: str, **_kwargs: object) -> _Proc:
        event = {
            "sessionID": "s1",
            "type": "text",
            "part": {
                "text": '{"decision":"request_changes","summary":"nope","required_actions":["fix"]}'
            },
        }
        import json

        return _Proc(json.dumps(event, sort_keys=True) + "\n")

    result = run_checks(
        tmp_path,
        phase="feature_done",
        checks=["reviewers"],
        feature_path=feature_path,
        start_agent_fn=_start_agent,
    )
    assert not result.ok
    assert result.failed_group == "reviewers"
    assert result.failed_check_id == "doc_review"
    assert "decision=request_changes" in result.output


def test_run_checks_check_id_must_match_enabled_groups(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase="iteration_end",
        checks=["fitness"],
        check_id="smoke",
    )
    assert not result.ok
    assert result.failed_group == "selection"
    assert result.failed_check_id == "smoke"


def test_run_checks_validate_group_executes(repo_root: Path) -> None:
    from engineeringagent.checks import run_checks

    result = run_checks(repo_root, phase="iteration_end", checks=["validate"])
    assert result.ok


def test_run_checks_accepts_harness_phase_enum(tmp_path: Path) -> None:
    from engineeringagent.checks import run_checks
    from engineeringagent.specs import HarnessCheckPhase

    _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                '    command: "python -c \\"print(\'ok\')\\""',
                "",
            ]
        ),
    )

    result = run_checks(
        tmp_path,
        phase=HarnessCheckPhase.ITERATION_END,
    )
    assert result.ok
