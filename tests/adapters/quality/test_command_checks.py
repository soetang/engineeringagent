from __future__ import annotations

from pathlib import Path

from engineeringagent.adapters.quality.command_checks import (
    PlannedCheck as CommandPlannedCheck,
)
from engineeringagent.adapters.quality.command_checks import (
    iter_planned_command_check_commands,
    plan_command_checks,
)
from engineeringagent.domain.quality import (
    ChangedPathsResult,
    HarnessCheckPhase,
    HarnessChecksDocument,
)
from engineeringagent.domain.specification import load_yaml


def _write_checks_yaml(tmp_path: Path, content: str) -> Path:
    checks_path = tmp_path / "harness" / "checks.yaml"
    checks_path.parent.mkdir(parents=True, exist_ok=True)
    checks_path.write_text(content, encoding="utf-8")
    return checks_path


def _load_checks_document(checks_path: Path) -> HarnessChecksDocument:
    payload = load_yaml(checks_path)
    return HarnessChecksDocument.model_validate(payload)


def test_plan_command_checks_manual_phase_skips(tmp_path: Path) -> None:
    """Skip command checks that are only declared for the manual phase."""
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "    when:",
                "      phase: manual",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.MANUAL,
        changed_paths=ChangedPathsResult(paths=(), run_all=False, reason=None),
    )

    assert [planned_check.model_dump() for planned_check in planned] == [
        {"check_id": "smoke", "decision": "skip", "reason": "manual"}
    ]


def test_plan_command_checks_runs_when_run_all_change_discovery_fallback(
    tmp_path: Path,
) -> None:
    """Run on-change command checks when change discovery falls back to run-all."""
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  ruff:",
                "    type: command",
                "    command: echo ruff",
                "    when:",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=(),
            run_all=True,
            reason="change_discovery_failed",
        ),
    )

    assert [planned_check.model_dump() for planned_check in planned] == [
        {
            "check_id": "ruff",
            "decision": "run",
            "reason": "change_discovery_failed",
        }
    ]


def test_plan_command_checks_runs_when_on_change_matches(tmp_path: Path) -> None:
    """Run command checks when the changed paths match the configured glob."""
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  ruff:",
                "    type: command",
                "    command: echo ruff",
                "    when:",
                "      on_change: ['src/**/*.py']",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.ITERATION_END,
        changed_paths=ChangedPathsResult(
            paths=("src/engineeringagent/cli.py",),
            run_all=False,
            reason=None,
        ),
    )

    assert planned[0].decision == "run"
    assert planned[0].reason == "matched_on_change"


def test_plan_command_checks_uses_defaults_when_phase(tmp_path: Path) -> None:
    """Apply default phase settings when a command check omits its own phase rule."""
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "defaults:",
                "  when:",
                "    phase: feature_done",
                "checks:",
                "  done_only:",
                "    type: command",
                "    command: echo done",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = plan_command_checks(
        doc,
        phase=HarnessCheckPhase.FEATURE_DONE,
        changed_paths=ChangedPathsResult(paths=(), run_all=True, reason=None),
    )

    assert [entry.check_id for entry in planned] == ["done_only"]


def test_iter_planned_command_check_commands_skips_non_run(tmp_path: Path) -> None:
    """Suppress emitted commands for planned checks that resolved to skip."""
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = [CommandPlannedCheck(check_id="smoke", decision="skip", reason="manual")]

    yielded = list(iter_planned_command_check_commands(doc, planned))
    assert not yielded


def test_iter_planned_command_check_commands_yields_run_command(
    tmp_path: Path,
) -> None:
    """Yield the command for each planned command check that will run."""
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  smoke:",
                "    type: command",
                "    command: echo hi",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = [CommandPlannedCheck(check_id="smoke", decision="run", reason="always")]

    yielded = list(iter_planned_command_check_commands(doc, planned))
    assert yielded == [("smoke", "echo hi")]


def test_iter_planned_command_check_commands_skips_non_command_defs(
    tmp_path: Path,
) -> None:
    """Ignore planned entries whose ids resolve to non-command definitions."""
    checks_path = _write_checks_yaml(
        tmp_path,
        "\n".join(
            [
                'contract_version: "1.0"',
                "checks:",
                "  doc_review:",
                "    type: reviewer",
                '    prompt_file: "harness/reviewers/prompts/doc_review.md"',
                "    when:",
                "      phase: feature_done",
                "",
            ]
        ),
    )
    doc = _load_checks_document(checks_path)

    planned = [
        CommandPlannedCheck(check_id="doc_review", decision="run", reason="always")
    ]

    yielded = list(iter_planned_command_check_commands(doc, planned))
    assert not yielded
