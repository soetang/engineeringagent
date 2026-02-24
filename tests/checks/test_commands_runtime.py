from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from engineeringagent.changed_paths import ChangedPathsResult
from engineeringagent.checks.commands.runtime import (
    RunPlannedCommandChecksRequest,
    plan_command_checks,
    run_planned_command_checks,
)
from engineeringagent.checks.fitness.runtime import plan_fitness_checks
from engineeringagent.checks.reviewers.runtime import plan_reviewer_checks
from engineeringagent.specs import HarnessCheckPhase, HarnessChecksDocument


def _doc(payload: dict[str, object]) -> HarnessChecksDocument:
    return HarnessChecksDocument.model_validate(payload)


def test_plan_command_checks_respects_on_change_and_manual_phase() -> None:
    doc = _doc(
        {
            "contract_version": "1.0",
            "checks": {
                "always": {
                    "type": "command",
                    "command": "echo hi",
                },
                "on_change": {
                    "type": "command",
                    "command": "echo hi",
                    "when": {"on_change": ["src/**"]},
                },
                "manual": {
                    "type": "command",
                    "command": "echo hi",
                    "when": {"phase": "manual"},
                },
            },
        }
    )

    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=("src/app.py",), run_all=False, reason=None
        ),
    )
    by_id = {entry.check_id: entry for entry in planned}
    assert by_id["always"].decision == "run"
    assert by_id["on_change"].decision == "run"

    planned_manual = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=ChangedPathsResult(
            paths=("src/app.py",), run_all=False, reason=None
        ),
    )
    assert [entry.check_id for entry in planned_manual] == ["manual"]
    assert planned_manual[0].decision == "skip"
    assert planned_manual[0].reason == "manual"


def test_run_planned_command_checks_failure_output_and_verbose(
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = _doc(
        {
            "contract_version": "1.0",
            "checks": {
                "smoke": {
                    "type": "command",
                    "command": "do the thing",
                }
            },
        }
    )

    def _run_shell_command(_root: Path, _command: str) -> object:
        return SimpleNamespace(returncode=2, stdout="out\n", stderr="err\n")

    monkeypatch.setattr(
        "engineeringagent.checks.commands.runtime.run_shell_command",
        _run_shell_command,
        raising=True,
    )

    result = run_planned_command_checks(
        RunPlannedCommandChecksRequest(
            project_root=tmp_path,
            doc=doc,
            phase=HarnessCheckPhase.ITERATION_END,
            changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
            verbose_output=True,
        )
    )
    assert not result.ok
    assert result.failed_check_id == "smoke"
    assert "[check:smoke] command=do the thing" in result.output
    assert "[check:smoke] returncode=2" in result.output
    assert "out" in result.output
    assert "err" in result.output
    assert len(result.command_invocations) == 1
    invocation = result.command_invocations[0]
    assert invocation.check_id == "smoke"
    assert invocation.command == "do the thing"
    assert invocation.returncode == 2
    assert invocation.duration_ms >= 0
    assert invocation.finished_monotonic_ns >= invocation.started_monotonic_ns

    captured = capsys.readouterr()
    assert captured.out == "out\nerr\n"


def test_run_planned_command_checks_snapshots_returncode_once(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    doc = _doc(
        {
            "contract_version": "1.0",
            "checks": {
                "smoke": {
                    "type": "command",
                    "command": "do the thing",
                }
            },
        }
    )

    class _FlakyProc:
        def __init__(self) -> None:
            self._returncode_reads = 0
            self.stdout = ""
            self.stderr = ""

        @property
        def returncode(self) -> int:
            self._returncode_reads += 1
            if self._returncode_reads == 1:
                return 0
            return 7

    def _run_shell_command(_root: Path, _command: str) -> object:
        return _FlakyProc()

    monkeypatch.setattr(
        "engineeringagent.checks.commands.runtime.run_shell_command",
        _run_shell_command,
        raising=True,
    )

    result = run_planned_command_checks(
        RunPlannedCommandChecksRequest(
            project_root=tmp_path,
            doc=doc,
            phase=HarnessCheckPhase.ITERATION_END,
            changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
            verbose_output=False,
        )
    )

    assert result.ok
    assert result.failed_check_id is None
    assert "[check:smoke] returncode=0" in result.output


@pytest.mark.parametrize(
    ("phase", "when", "changed_paths", "expected"),
    [
        (
            HarnessCheckPhase.FEATURE_DONE,
            {"phase": "feature_done"},
            ChangedPathsResult(paths=("README.md",), run_all=False, reason=None),
            ("run", "always_run_no_on_change"),
        ),
        (
            HarnessCheckPhase.FEATURE_DONE,
            {"phase": "feature_done", "on_change": ["src/**"]},
            ChangedPathsResult(paths=("src/app.py",), run_all=False, reason=None),
            ("run", "matched_on_change"),
        ),
        (
            HarnessCheckPhase.FEATURE_DONE,
            {"phase": "feature_done", "on_change": ["src/**"]},
            ChangedPathsResult(paths=("README.md",), run_all=False, reason=None),
            ("skip", "no_on_change_match"),
        ),
        (
            HarnessCheckPhase.FEATURE_DONE,
            {"phase": "feature_done", "on_change": ["src/**"]},
            ChangedPathsResult(paths=(), run_all=True, reason="fallback"),
            ("run", "fallback"),
        ),
        (
            HarnessCheckPhase.MANUAL,
            {"phase": "manual"},
            ChangedPathsResult(paths=("src/app.py",), run_all=False, reason=None),
            ("skip", "manual"),
        ),
    ],
)
def test_planning_policy_parity_across_check_types(
    phase: HarnessCheckPhase,
    when: dict[str, object],
    changed_paths: ChangedPathsResult,
    expected: tuple[str, str],
) -> None:
    doc = _doc(
        {
            "contract_version": "1.0",
            "checks": {
                "cmd": {
                    "type": "command",
                    "command": "echo ok",
                    "when": when,
                },
                "fit": {
                    "type": "fitness",
                    "scope": "all",
                    "when": when,
                },
                "rev": {
                    "type": "reviewer",
                    "prompt_file": "harness/reviewers/prompts/doc_review.md",
                    "when": when,
                },
            },
        }
    )

    command_entry = plan_command_checks(
        doc,
        phase=phase,
        changed_paths=changed_paths,
    )[0]
    fitness_entry = plan_fitness_checks(
        doc,
        phase=phase,
        changed_paths=changed_paths,
    )[0]
    reviewer_entry = plan_reviewer_checks(
        doc,
        phase=phase,
        changed_paths=changed_paths,
    )[0]

    assert (command_entry.decision, command_entry.reason) == expected
    assert (fitness_entry.decision, fitness_entry.reason) == expected
    assert (reviewer_entry.decision, reviewer_entry.reason) == expected
