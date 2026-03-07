from __future__ import annotations

from pathlib import Path
from typing import NamedTuple, Sequence, cast

from .. import checks as checks_module
from ..loop import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    run_loop_controller,
)


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
    """Execute the loop runner for one or more feature files."""
    resolved_args = _coerce_handler_args(args)
    if resolved_args.run_all and resolved_args.feature_paths:
        print("run input error: positional feature paths cannot be used with --all")
        return 1
    if not resolved_args.run_all and not resolved_args.feature_paths:
        print("run input error: provide one or more feature paths, or use --all")
        return 1

    project_root = Path(resolved_args.project_root).resolve()

    if resolved_args.run_all:
        _, checks_error = checks_module.load_harness_checks_document(
            project_root,
            error_prefix="run config error",
            missing_context=" (required for --all)",
        )
        if checks_error is not None:
            print(checks_error)
            return 1

    config = build_run_config(
        project_root=project_root,
        feature_paths=resolved_args.feature_paths,
        options=RunConfigOptions(
            resolved_args.dry_run,
            resolved_args.run_all,
            resolved_args.max_iterations,
            resolved_args.allow_dirty,
            resolved_args.verbose_output,
        ),
    )
    loop_run = build_loop_run(config)
    return run_loop_controller(loop_run)
