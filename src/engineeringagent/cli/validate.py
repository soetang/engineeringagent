from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ..application import ValidateRepositoryRequest
from ..bootstrap import AppFactory

_HandlerArgs = SimpleNamespace


def cmd_validate(args: _HandlerArgs) -> int:
    """Run feature spec validation and print failures."""
    project_root = Path(args.project_root).resolve()
    result = AppFactory(project_root).build_validation_service().run(
        ValidateRepositoryRequest(
            project_root=project_root,
            schema_only=bool(getattr(args, "schema_only", False)),
        )
    )
    if not result.ok:
        for line in result.messages:
            print(line)
        return 1

    print("spec validation: ok")
    return 0
