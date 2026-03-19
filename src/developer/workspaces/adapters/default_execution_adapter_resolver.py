"""Default execution-adapter resolution for workspace targets."""

from developer.workspaces.adapters.local_path_execution_adapter import (
    LocalPathWorkspaceExecutionAdapter,
)
from developer.workspaces.models import ExecutionTarget
from developer.workspaces.protocols import (
    WorkspaceExecutionAdapter,
    WorkspaceExecutionAdapterResolver,
)


class DefaultWorkspaceExecutionAdapterResolver(WorkspaceExecutionAdapterResolver):
    """Resolve the built-in execution adapter for a workspace target."""

    def resolve(self, target: ExecutionTarget) -> WorkspaceExecutionAdapter:
        """Return the execution adapter for the requested target."""
        if target.kind == "local_path":
            return LocalPathWorkspaceExecutionAdapter()
        raise ValueError(f"Unsupported execution target kind: {target.kind}")
