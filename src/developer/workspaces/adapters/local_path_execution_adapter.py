"""Execution adapter for local-path workspaces."""

import os
from collections.abc import Generator
from contextlib import contextmanager
from pathlib import Path

from developer.workspaces.models import (
    RunRequest,
    WorkspaceRunnableResult,
    WorkspaceSession,
)
from developer.workspaces.protocols import (
    WorkspaceExecutionAdapter,
    WorkspaceRunnableAgent,
)


class LocalPathWorkspaceExecutionAdapter(WorkspaceExecutionAdapter):
    """Run a workspace workflow with the workspace path as the active cwd."""

    def run(
        self,
        workspace: WorkspaceSession,
        request: RunRequest,
        agent: WorkspaceRunnableAgent,
    ) -> WorkspaceRunnableResult:
        """Execute a workflow in a local-path workspace."""
        if workspace.execution_target.kind != "local_path":
            raise ValueError(
                "LocalPathWorkspaceExecutionAdapter requires local_path target"
            )

        with _working_directory(Path(workspace.execution_target.location)):
            return agent.run(request=request, workspace=workspace)


@contextmanager
def _working_directory(path: Path) -> Generator[None, None, None]:
    """Temporarily change the process working directory."""
    previous_cwd = Path.cwd()
    os.chdir(path)
    try:
        yield
    finally:
        os.chdir(previous_cwd)
