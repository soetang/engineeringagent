from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from ...application.contracts.workspace_recovery import RecoverWorkspaceRequest
from ...bootstrap import AppFactory

_HandlerArgs = SimpleNamespace


def cmd_workspace_reset(args: _HandlerArgs) -> int:
    """Reset one feature workspace to the last accepted commit."""
    project_root = Path(args.project_root).resolve()
    result = AppFactory(project_root).build_workspace_recovery_service().run(
        RecoverWorkspaceRequest(
            project_root=project_root,
            feature_id=args.feature_id,
            last_accepted_commit=args.last_accepted_commit,
        )
    )
    print(result.message)
    return 0 if result.ok else 1
