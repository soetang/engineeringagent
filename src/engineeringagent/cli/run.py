from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from .. import checks as checks_module
from ..loop import (
    RunConfigOptions,
    build_loop_run,
    build_run_config,
    run_loop_controller,
)

_HandlerArgs = SimpleNamespace

__all__ = ["cmd_run"]


def cmd_run(args: _HandlerArgs) -> int:
    """Execute the loop runner for one or more feature files."""
    if args.run_all and args.feature_paths:
        print("run input error: positional feature paths cannot be used with --all")
        return 1
    if not args.run_all and not args.feature_paths:
        print("run input error: provide one or more feature paths, or use --all")
        return 1

    project_root = Path(args.project_root).resolve()

    if args.run_all:
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
        feature_paths=args.feature_paths,
        options=RunConfigOptions(
            args.dry_run,
            args.run_all,
            args.max_iterations,
            args.allow_dirty,
            args.verbose_output,
        ),
    )
    loop_run = build_loop_run(config)
    return run_loop_controller(loop_run)
