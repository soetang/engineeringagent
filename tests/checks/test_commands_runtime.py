from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import TYPE_CHECKING

import pytest


if TYPE_CHECKING:
    from engineeringagent.specs import HarnessChecksDocument


def _doc(payload: dict[str, object]) -> HarnessChecksDocument:
    from engineeringagent.specs import HarnessChecksDocument

    return HarnessChecksDocument.model_validate(payload)


def test_plan_command_checks_respects_on_change_and_manual_phase() -> None:
    from engineeringagent.changed_paths import ChangedPathsResult
    from engineeringagent.checks.commands.runtime import plan_command_checks
    from engineeringagent.specs import HarnessCheckPhase

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
) -> None:
    from engineeringagent.changed_paths import ChangedPathsResult
    from engineeringagent.checks.commands.runtime import RunPlannedCommandChecksRequest
    from engineeringagent.checks.commands.runtime import run_planned_command_checks
    from engineeringagent.specs import HarnessCheckPhase

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

    ok, failed, output = run_planned_command_checks(
        RunPlannedCommandChecksRequest(
            project_root=tmp_path,
            doc=doc,
            phase=HarnessCheckPhase.ITERATION_END,
            changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
            verbose_output=True,
        ),
        run_shell_command=_run_shell_command,
    )
    assert not ok
    assert failed == "smoke"
    assert "[check:smoke] command=do the thing" in output
    assert "[check:smoke] returncode=2" in output
    assert "out" in output
    assert "err" in output

    captured = capsys.readouterr()
    assert captured.out == "out\nerr\n"
