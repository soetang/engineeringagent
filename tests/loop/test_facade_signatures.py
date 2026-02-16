from __future__ import annotations

from engineeringagent.loop_runtime.facade_signatures import (
    PRINT_SUMMARY_SIGNATURE,
    RUN_LOOP_SIGNATURE,
    bind_facade_call,
)


def test_bind_facade_call_applies_defaults_for_run_loop_signature() -> None:
    bound = bind_facade_call(
        RUN_LOOP_SIGNATURE,
        args=("root", ("docs/spec/features/FEAT-001.yaml",), "precommit", True),
        kwargs={},
    )

    assert bound == {
        "project_root": "root",
        "feature_paths": ("docs/spec/features/FEAT-001.yaml",),
        "gate_profile": "precommit",
        "dry_run": True,
        "run_all": False,
        "max_iterations": 50,
        "allow_dirty": False,
        "verbose_output": False,
    }


def test_bind_facade_call_applies_none_defaults_for_print_summary_signature() -> None:
    bound = bind_facade_call(
        PRINT_SUMMARY_SIGNATURE,
        args=("FEAT-001", {"result": "ok"}, None, 1, "next"),
        kwargs={},
    )

    assert bound["feature_id"] == "FEAT-001"
    assert bound["attempt"] == 1
    assert bound["selected_path"] is None
    assert bound["verification_status"] is None
    assert bound["failed_reviewer_id"] is None
