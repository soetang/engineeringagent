from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Sequence, cast

from engineeringagent.application import RunLoopRequest
from engineeringagent.bootstrap import AppFactory


class _HandlerArgs(NamedTuple):
    project_root: str | Path
    feature_paths: Sequence[str | Path]
    run_all: bool
    dry_run: bool
    max_iterations: int
    allow_dirty: bool
    verbose_output: bool

__all__ = ["cmd_run"]


def _coerce_handler_args(args: object) -> _HandlerArgs:
    """Normalize CLI handler input into a statically typed record."""
    return _HandlerArgs(
        project_root=cast(str | Path, getattr(args, "project_root")),
        feature_paths=cast(Sequence[str | Path], getattr(args, "feature_paths")),
        run_all=bool(getattr(args, "run_all")),
        dry_run=bool(getattr(args, "dry_run")),
        max_iterations=cast(int, getattr(args, "max_iterations")),
        allow_dirty=bool(getattr(args, "allow_dirty")),
        verbose_output=bool(getattr(args, "verbose_output")),
    )


def cmd_run(args: object) -> int:
    """Execute the loop runner for one or more feature entrypoints."""
    resolved_args = _coerce_handler_args(args)

    project_root = Path(resolved_args.project_root).resolve()
    result = AppFactory(project_root).build_run_loop_service().run(
        RunLoopRequest(
            project_root=project_root,
            feature_paths=tuple(resolved_args.feature_paths),
            run_all=resolved_args.run_all,
            dry_run=resolved_args.dry_run,
            max_iterations=resolved_args.max_iterations,
            allow_dirty=resolved_args.allow_dirty,
            verbose_output=resolved_args.verbose_output,
        )
    )
    if result.message is not None:
        print(result.message)
    return result.exit_code
