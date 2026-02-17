"""Run-loop terminal presentation helpers."""

from __future__ import annotations

import sys
from typing import TextIO

from pydantic import BaseModel, ConfigDict

ANSI_RESET = "\x1b[0m"
ANSI_BOLD = "\x1b[1m"
ANSI_GREEN = "\x1b[32m"
ANSI_RED = "\x1b[31m"
ANSI_YELLOW = "\x1b[33m"


def _stdout_is_tty(stdout: TextIO) -> bool:
    isatty = getattr(stdout, "isatty", None)
    if not callable(isatty):
        return False
    try:
        return bool(isatty())
    except Exception:
        return False


def tty_supports_ansi(
    *,
    stdout: TextIO | None = None,
) -> bool:
    """Return whether run-loop output should use ANSI styling."""
    active_stdout = stdout or sys.stdout
    if not _stdout_is_tty(active_stdout):
        return False
    return True


class RunOutputPresenter(BaseModel):
    """Render run-loop summary lines with optional ANSI accents."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    use_ansi: bool

    @classmethod
    def for_current_terminal(cls) -> "RunOutputPresenter":
        return cls(use_ansi=tty_supports_ansi())

    def format_summary_suffix(self, result: str) -> str:
        if not self.use_ansi:
            return ""
        if result == "passed":
            return f" {ANSI_GREEN}{ANSI_BOLD}[ok]{ANSI_RESET}"
        if result == "failed":
            return f" {ANSI_RED}{ANSI_BOLD}[failed]{ANSI_RESET}"
        return f" {ANSI_YELLOW}{ANSI_BOLD}[{result}]{ANSI_RESET}"

    def format_failed_gate_line(self, failed_gate: str) -> str:
        if not self.use_ansi:
            return f"Failed gate: {failed_gate}"
        return f"{ANSI_RED}{ANSI_BOLD}Failed gate:{ANSI_RESET} {failed_gate}"

    def format_iteration_passed_line(self) -> str:
        if not self.use_ansi:
            return "✅ Passed"
        return f"✅ {ANSI_GREEN}{ANSI_BOLD}Passed{ANSI_RESET}"

    def format_iteration_failed_line(self, failed_gate: str | None) -> str:
        gate_value = failed_gate or "unknown"
        if not self.use_ansi:
            return f"❌ Failed: gate={gate_value}"
        return (
            f"❌ {ANSI_RED}{ANSI_BOLD}Failed{ANSI_RESET}: "
            f"{ANSI_RED}gate={gate_value}{ANSI_RESET}"
        )
