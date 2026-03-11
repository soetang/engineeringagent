from __future__ import annotations

# pylint: disable=missing-function-docstring,protected-access
# pyright: reportArgumentType=false, reportAttributeAccessIssue=false
from pathlib import Path
from types import SimpleNamespace

import engineeringagent.loop as loop_module
from engineeringagent.domain.audit import IterationSummaryInputs


def test_commit_feature_completion_reports_success_output(monkeypatch) -> None:
    """Completion commit helper should return success when a commit is created."""

    class _Gateway:
        def commit(self, request):  # noqa: ANN001
            assert request.message == "feat: complete FEAT-001"
            return SimpleNamespace(
                commit_created=True,
                failure_stage=None,
                stdout="stdout\n",
                stderr="stderr\n",
            )

    monkeypatch.setattr(
        loop_module,
        "_build_version_control_gateway",
        lambda project_root: _Gateway(),
    )

    result = loop_module._commit_feature_completion(
        Path("/tmp/project"),
        {"expected_commit_subject": "feat: complete FEAT-001"},
    )

    assert result == (True, None, "stdout\nstderr\n")


def test_handle_dry_run_reports_no_pending_features_for_explicit_paths(
    monkeypatch,
) -> None:
    """Dry-run should stop cleanly when explicit paths resolve to no pending work."""
    captured: list[IterationSummaryInputs] = []

    monkeypatch.setattr(loop_module, "pending_features", lambda resolved_paths: [])
    monkeypatch.setattr(loop_module, "print_summary", captured.append)

    exit_code = loop_module._handle_dry_run(
        resolved_paths=[Path("docs/spec/features/FEAT-001/spec.yaml")],
        run_all=False,
        dry_run=True,
    )

    assert exit_code == 0
    assert captured == [
        IterationSummaryInputs(
            feature_id=None,
            result="dry_run",
            failed_gate=None,
            attempt=None,
            next_action="stop",
        )
    ]


def test_default_iteration_report_observers_and_persist_report_use_app_factory(
    monkeypatch,
) -> None:
    """Default observer wiring should persist reports through the app factory."""
    report = SimpleNamespace(
        telemetry_inputs=SimpleNamespace(
            iteration_inputs=SimpleNamespace(project_root=Path("/tmp/project"))
        ),
        feature_id="FEAT-001",
        model_dump=lambda mode="json": {"result": "passed", "mode": mode},
    )
    observed: dict[str, object] = {}

    monkeypatch.setattr(
        loop_module,
        "build_default_iteration_report_observers",
        lambda dependencies: observed.setdefault("dependencies", dependencies)
        or ("observer",),
    )
    monkeypatch.setattr(
        loop_module,
        "AppFactory",
        lambda project_root: SimpleNamespace(
            build_progress_journal=lambda: SimpleNamespace(
                write_iteration_report=lambda **kwargs: observed.setdefault(
                    "persist_kwargs", kwargs
                )
            )
        ),
    )

    observers = loop_module._default_iteration_report_observers()
    loop_module._persist_iteration_report(report)

    assert observers == observed["dependencies"]
    dependencies = observed["dependencies"]
    assert dependencies.git_head_resolver is loop_module.git_head_short
    assert dependencies.print_summary is loop_module.print_summary
    assert observed["persist_kwargs"] == {
        "project_root": Path("/tmp/project"),
        "feature_id": "FEAT-001",
        "payload": {"result": "passed", "mode": "json"},
    }
