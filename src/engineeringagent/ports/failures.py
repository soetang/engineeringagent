"""Shared port failure types."""

from __future__ import annotations


class PortFailure(Exception):
    """Raised when an application-facing port cannot satisfy a request."""

    def __init__(self, port_name: str, message: str) -> None:
        super().__init__(message)
        self.port_name = port_name
        self.message = message


class ValidationFailure(PortFailure):
    """Raised when a validation-oriented port rejects its inputs or source data."""


class ExecutionFailure(PortFailure):
    """Raised when an execution-oriented port cannot complete a request."""


class WorkspaceFailure(PortFailure):
    """Raised when a workspace-oriented port cannot complete a request."""
