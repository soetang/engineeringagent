from __future__ import annotations

from pathlib import Path

from engineeringagent.checks import run_checks

def test_run_checks_check_id_without_harness_doc_fails_deterministically(
    tmp_path: Path,
) -> None:
    """Check-id selection without a loaded harness document should fail predictably."""
    result = run_checks(tmp_path, phase="iteration_end", checks=["validate"], check_id="smoke")
    assert not result.ok
    assert result.failed_check_id == "smoke"
