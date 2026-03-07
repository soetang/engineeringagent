"""Shared terminal capability helpers."""

from __future__ import annotations

import sys


def stdout_is_tty(stdout: object | None = None) -> bool:
    """Return True when stdout looks like an interactive TTY."""
    active_stdout = stdout if stdout is not None else sys.stdout
    isatty = getattr(active_stdout, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except (OSError, ValueError, RuntimeError):
        return False
