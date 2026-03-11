from __future__ import annotations

from pathlib import Path

from engineeringagent import changed_paths
from engineeringagent.ports import (
    CommitRequest,
    CommitResult,
    DiffSummary,
    VersionControlFailure,
    WorktreeStatus,
)


class StubVersionControlGateway:
    def __init__(
        self,
        *,
        summary_text: str = "",
        error: Exception | None = None,
    ) -> None:
        self.summary_text = summary_text
        self.error = error
        self.calls: list[tuple[Path, str | None, str | None]] = []

    def diff_against_base(
        self,
        project_root: Path,
        *,
        base_ref: str | None = None,
        head_ref: str | None = None,
    ) -> DiffSummary:
        self.calls.append((project_root, base_ref, head_ref))
        if self.error is not None:
            raise self.error
        return DiffSummary(
            base_ref=base_ref,
            head_ref=head_ref,
            summary_text=self.summary_text,
        )

    def head_commit(self, project_root: Path) -> str | None:
        return None

    def worktree_status(self, project_root: Path) -> WorktreeStatus:
        return WorktreeStatus(dirty=False, stdout="", stderr="")

    def commit(self, request: CommitRequest) -> CommitResult:
        return CommitResult(
            commit_created=False,
            commit_sha=None,
            stdout="",
            stderr="",
            failure_stage="git_commit",
        )


def test_collect_changed_paths_falls_back_when_git_diff_fails(
    tmp_path: Path,
) -> None:
    """Fall back to run-all semantics when the diff query fails."""
    gateway = StubVersionControlGateway(error=VersionControlFailure("boom"))

    result = changed_paths.collect_changed_paths(tmp_path, version_control=gateway)

    assert result.paths == ()
    assert result.run_all is True
    assert result.reason == changed_paths.FALLBACK_CHANGE_DISCOVERY_REASON


def test_collect_changed_paths_parses_rename_and_normalizes_separators(
    tmp_path: Path,
) -> None:
    """Parse rename rows and normalize path separators to POSIX form."""
    # Include an internal blank line (not just trailing newline) so the
    # implementation exercises the `if not line.strip(): continue` branch.
    stdout = "\n".join(
        [
            "A\tsrc\\engineeringagent\\cli.py",
            " ",
            "R100\tsrc\\old.py\tsrc\\new.py",
        ]
    )

    gateway = StubVersionControlGateway(summary_text=stdout)

    result = changed_paths.collect_changed_paths(tmp_path, version_control=gateway)

    assert result.run_all is False
    assert result.reason is None
    assert result.paths == (
        "src/engineeringagent/cli.py",
        "src/new.py",
        "src/old.py",
    )


def test_collect_changed_paths_includes_base_and_head_when_provided(
    tmp_path: Path,
) -> None:
    """Forward the requested revision range to the version-control gateway."""
    gateway = StubVersionControlGateway(summary_text="A\tsrc/app.py\n")

    result = changed_paths.collect_changed_paths(
        tmp_path,
        base="BASE",
        head="HEAD",
        version_control=gateway,
    )

    assert result.run_all is False
    assert result.paths == ("src/app.py",)
    assert gateway.calls == [(tmp_path, "BASE", "HEAD")]


def test_collect_changed_paths_falls_back_on_malformed_diff_output(
    tmp_path: Path,
) -> None:
    """Treat malformed diff rows as a signal to run all checks."""
    stdout = "NOT_A_STATUS_LINE_WITH_TABS\n"
    gateway = StubVersionControlGateway(summary_text=stdout)

    result = changed_paths.collect_changed_paths(tmp_path, version_control=gateway)

    assert result.run_all is True
    assert result.paths == ()
    assert result.reason == changed_paths.FALLBACK_CHANGE_DISCOVERY_REASON


def test_collect_changed_paths_falls_back_on_malformed_rename_record(
    tmp_path: Path,
) -> None:
    """Treat malformed rename rows as a signal to run all checks."""
    stdout = "R100\tsrc/old.py\n"
    gateway = StubVersionControlGateway(summary_text=stdout)

    result = changed_paths.collect_changed_paths(tmp_path, version_control=gateway)

    assert result.run_all is True
    assert result.paths == ()
    assert result.reason == changed_paths.FALLBACK_CHANGE_DISCOVERY_REASON
