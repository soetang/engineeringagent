"""Adapter that executes checks through the stable repository checks surface."""

from __future__ import annotations

from engineeringagent import checks as checks_domain
from engineeringagent.ports import ChecksRunRequest, ChecksRunner


class RuntimeChecksRunner(ChecksRunner):
    """Run checks through the packaged checks runtime facade."""

    def run(self, request: ChecksRunRequest) -> checks_domain.ChecksRunResult:
        """Execute one checks request through the top-level checks facade."""
        return checks_domain.run_checks(
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
        return checks_domain.reviewers_group_selected(selected_checks)
