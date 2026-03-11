"""Adapter that executes checks through the application-owned runtime."""

from __future__ import annotations

from engineeringagent.application.checks.runtime import run_checks
from engineeringagent.domain.quality import ChecksRunResult, reviewers_group_selected
from engineeringagent.ports import ChecksRunRequest, ChecksRunner


class RuntimeChecksRunner(ChecksRunner):
    """Run checks through the packaged checks runtime."""

    def run(self, request: ChecksRunRequest) -> ChecksRunResult:
        """Execute one checks request through the concrete runtime module."""
        return run_checks(
            request.project_root,
            phase=request.phase,
            checks=request.selected_checks,
            check_id=request.check_id,
            feature_path=request.feature_path,
            verbose_output=request.verbose_output,
            base=request.base,
            head=request.head,
            dry_run=request.dry_run,
        )

    def reviewers_group_selected(self, selected_checks: list[str] | None) -> bool:
        """Return whether the selected groups require reviewer context."""
        return reviewers_group_selected(selected_checks)
