from __future__ import annotations

import subprocess
from dataclasses import dataclass
from pathlib import Path


PROBE_TOKEN = "PERMISSION_OK"
PROBE_PROMPT = "Run exactly: git status --short. If it succeeds, reply PERMISSION_OK."
PERMISSION_REJECTION_MARKERS = (
    "permission requested",
    "auto-reject",
    "auto reject",
    "was not granted",
)


@dataclass(frozen=True)
class PermissionProbeResult:
    ok: bool
    reason: str
    returncode: int
    output: str


def output_has_permission_rejection(output: str) -> bool:
    lowered = output.lower()
    return any(marker in lowered for marker in PERMISSION_REJECTION_MARKERS)


def evaluate_permission_probe(returncode: int, output: str, token: str = PROBE_TOKEN) -> PermissionProbeResult:
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
    command = ["opencode", "run", "--agent", "build", PROBE_PROMPT]
    try:
        proc = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
        )
    except FileNotFoundError:
        return PermissionProbeResult(
            ok=False,
            reason="opencode CLI not found in PATH",
            returncode=127,
            output="",
        )

    output = (proc.stdout or "") + (proc.stderr or "")
    return evaluate_permission_probe(returncode=proc.returncode, output=output)
