from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from .. import checks as checks_module

_HandlerArgs = SimpleNamespace


def cmd_validate(args: _HandlerArgs) -> int:
    """Run feature spec validation and print failures."""
    project_root = Path(args.project_root).resolve()
    result = checks_module.run_checks(
        project_root,
        phase="manual",
        checks=["validate"],
        schema_only=bool(getattr(args, "schema_only", False)),
    )
    if not result.ok:
        if result.output:
            for line in result.output.splitlines():
                print(line)
        return 1

    print("spec validation: ok")
    return 0
