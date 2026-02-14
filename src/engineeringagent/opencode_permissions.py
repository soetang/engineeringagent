from __future__ import annotations

from pathlib import Path

from pydantic import BaseModel, ConfigDict

from .opencode.client import start_agent


PROBE_TOKEN = "PERMISSION_OK"
PROBE_PROMPT = "Run exactly: git status --short. If it succeeds, reply PERMISSION_OK."
PERMISSION_REMEDIATION_HINT = (
    "hint: ensure .opencode/agents/build.md and opencode.json both set "
    "build permissions to allow-all"
)
PERMISSION_REJECTION_MARKERS = (
    "permission requested",
    "auto-reject",
    "auto reject",
    "was not granted",
)


class PermissionProbeResult(BaseModel):
    model_config = ConfigDict(frozen=True, extra="forbid")

    ok: bool
    reason: str
    returncode: int
    output: str


def output_has_permission_rejection(output: str) -> bool:
    """Detect permission-rejection markers in OpenCode output.

    Args:
        output: Combined stdout and stderr text from OpenCode.

    Returns:
        True when known rejection markers are present.
    """
    lowered = output.lower()
    return any(marker in lowered for marker in PERMISSION_REJECTION_MARKERS)


def evaluate_permission_probe(
    returncode: int, output: str, token: str = PROBE_TOKEN
) -> PermissionProbeResult:
    """Evaluate probe process output against success criteria.

    Args:
        returncode: Exit code returned by the probe process.
        output: Combined stdout and stderr text from OpenCode.
        token: Required success token expected in output.

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
    if returncode != 0:
        return PermissionProbeResult(
            ok=False,
            reason=f"opencode exited with status {returncode}",
            returncode=returncode,
            output=output,
        )
    if token not in output:
        return PermissionProbeResult(
            ok=False,
            reason=f"success token '{token}' not found in opencode output",
            returncode=returncode,
            output=output,
        )
    return PermissionProbeResult(
        ok=True,
        reason="permission probe passed",
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
    try:
        proc = start_agent(project_root, PROBE_PROMPT, agent="build")
    except FileNotFoundError:
        return PermissionProbeResult(
            ok=False,
            reason="opencode CLI not found in PATH",
            returncode=127,
            output="",
        )

    output = (proc.stdout or "") + (proc.stderr or "")
    return evaluate_permission_probe(returncode=proc.returncode, output=output)
