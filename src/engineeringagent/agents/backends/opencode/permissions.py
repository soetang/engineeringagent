from __future__ import annotations

import re
from pathlib import Path

from pydantic import BaseModel, ConfigDict

from engineeringagent.agents_defaults import DEFAULT_OPENCODE_AGENT

from .client import start_agent


PROBE_COMMAND = "git status --short"
PROBE_TOKEN = "PERMISSION_OK"
PROBE_DENIED_TOKEN = "PERMISSION_DENIED"
PROBE_MAX_ATTEMPTS = 3
PROBE_PROMPT = (
    "Run exactly this bash command: "
    f"{PROBE_COMMAND} >/dev/null 2>&1 && printf '{PROBE_TOKEN}' || printf '{PROBE_DENIED_TOKEN}'. "
    "Respond with exactly one token and nothing else: "
    f"{PROBE_TOKEN} or {PROBE_DENIED_TOKEN}."
)
PERMISSION_REMEDIATION_HINT = (
    "hint: ensure .opencode/agents/engineeringagent.md grants allow-all permissions "
    "for the engineeringagent OpenCode agent"
)
PERMISSION_REJECTION_LINE_PATTERNS = (
    re.compile(
        r"^\s*(?:\[[^\]]+\]\s*)?(?:stderr:\s*)?(?:error:\s*)?permission requested(?::\s*bash\b|(?: for)? (?:the )?bash command\b)",
        re.IGNORECASE,
    ),
    re.compile(
        r"^\s*(?:\[[^\]]+\]\s*)?(?:stderr:\s*)?(?:error:\s*)?permission .*was not granted\b",
        re.IGNORECASE,
    ),
)
ANSI_ESCAPE_PATTERN = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


class PermissionProbeResult(BaseModel):
    """Structured evaluation result for the OpenCode permission probe."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    reason: str
    returncode: int
    output: str


def _extract_probe_decision_token(output: str) -> str | None:
    token: str | None = None
    for line in output.splitlines():
        cleaned = ANSI_ESCAPE_PATTERN.sub("", line).strip()
        if cleaned not in (PROBE_TOKEN, PROBE_DENIED_TOKEN):
            continue
        if token is None:
            token = cleaned
            continue
        if token != cleaned:
            return None

    return token


def output_has_permission_rejection(output: str) -> bool:
    """Detect permission-rejection markers in OpenCode output.

    Args:
        output: Combined stdout and stderr text from OpenCode.

    Returns:
        True when known rejection markers are present.
    """
    for line in output.splitlines():
        if any(pattern.search(line) for pattern in PERMISSION_REJECTION_LINE_PATTERNS):
            return True
    return False


def evaluate_permission_probe(
    returncode: int,
    output: str,
    ok_token: str = PROBE_TOKEN,
    denied_token: str = PROBE_DENIED_TOKEN,
) -> PermissionProbeResult:
    """Evaluate probe process output against success criteria.

    Args:
        returncode: Exit code returned by the probe process.
        output: Combined stdout and stderr text from OpenCode.
        ok_token: Explicit allow decision token expected in output.
        denied_token: Explicit deny decision token expected in output.

    Returns:
        Structured evaluation result with pass/fail reason.
    """
    if output_has_permission_rejection(output):
        return PermissionProbeResult(
            ok=False,
            reason="permission request rejection detected in opencode output",
            returncode=returncode,
            output=output,
        )

    decision_token = _extract_probe_decision_token(output)

    if decision_token == denied_token:
        return PermissionProbeResult(
            ok=False,
            reason="permission probe reported explicit denial token",
            returncode=returncode,
            output=output,
        )

    if decision_token == ok_token:
        if returncode == 0:
            return PermissionProbeResult(
                ok=True,
                reason="permission probe passed with explicit allow token",
                returncode=returncode,
                output=output,
            )

        return PermissionProbeResult(
            ok=False,
            reason=f"opencode exited with status {returncode}",
            returncode=returncode,
            output=output,
        )

    if returncode != 0:
        return PermissionProbeResult(
            ok=False,
            reason=(
                f"opencode exited with status {returncode} without explicit decision token"
            ),
            returncode=returncode,
            output=output,
        )

    return PermissionProbeResult(
        ok=False,
        reason=(
            "expected exactly one decision token "
            f"('{ok_token}' or '{denied_token}') in opencode output"
        ),
        returncode=returncode,
        output=output,
    )


def run_permission_probe(project_root: Path) -> PermissionProbeResult:
    """Run the OpenCode permission probe command.

    Args:
        project_root: Repository root where the probe is executed.

    Returns:
        Probe evaluation result describing pass/fail details.
    """
    last_result: PermissionProbeResult | None = None

    for _ in range(1, PROBE_MAX_ATTEMPTS + 1):
        try:
            proc = start_agent(
                project_root,
                PROBE_PROMPT,
                agent=DEFAULT_OPENCODE_AGENT,
            )
        except FileNotFoundError:
            return PermissionProbeResult(
                ok=False,
                reason="opencode CLI not found in PATH",
                returncode=127,
                output="",
            )

        output = (proc.stdout or "") + (proc.stderr or "")
        result = evaluate_permission_probe(returncode=proc.returncode, output=output)
        decision_token = _extract_probe_decision_token(output)
        if decision_token is not None:
            return result

        last_result = result

    assert last_result is not None
    return PermissionProbeResult(
        ok=False,
        reason=(f"{last_result.reason} (after {PROBE_MAX_ATTEMPTS} probe attempts)"),
        returncode=last_result.returncode,
        output=last_result.output,
    )
