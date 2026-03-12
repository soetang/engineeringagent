from __future__ import annotations

import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any

from pydantic import BaseModel, ConfigDict

from .model_ids import normalize_codex_model_id


DEFAULT_CODEX_SANDBOX = "workspace-write"


class CodexExecResult(BaseModel):
    """Structured Codex invocation result for backend adapters."""

    model_config = ConfigDict(frozen=True)

    args: list[str]
    returncode: int
    stdout: str
    stderr: str
    output_last_message: str


class CodexExecConfig(BaseModel):
    """Execution options for `codex exec`."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    output_schema: dict[str, Any] | None = None
    profile: str | None = None
    model: str | None = None
    sandbox: str = DEFAULT_CODEX_SANDBOX


def run_codex_exec(
    project_root: Path,
    prompt: str,
    *,
    config: CodexExecConfig | None = None,
) -> CodexExecResult:
    """Run `codex exec` and capture the canonical output-last-message payload."""
    effective_config = config or CodexExecConfig()

    with tempfile.TemporaryDirectory(prefix="engineeringagent-codex-") as temp_dir:
        temp_path = Path(temp_dir)
        output_last_message_path = temp_path / "output-last-message.txt"

        command: list[str] = [
            "codex",
            "exec",
            "--sandbox",
            effective_config.sandbox,
            "--output-last-message",
            str(output_last_message_path),
        ]
        if effective_config.profile:
            command.extend(["--profile", effective_config.profile])
        if effective_config.model:
            normalized_model = normalize_codex_model_id(effective_config.model)
            if normalized_model:
                command.extend(["--model", normalized_model])

        if effective_config.output_schema is not None:
            output_schema_path = temp_path / "output-schema.json"
            output_schema_path.write_text(
                json.dumps(
                    effective_config.output_schema,
                    indent=2,
                    sort_keys=True,
                    ensure_ascii=True,
                ),
                encoding="utf-8",
            )
            command.extend(["--output-schema", str(output_schema_path)])

        command.append(prompt)

        proc = subprocess.run(
            command,
            cwd=project_root,
            capture_output=True,
            text=True,
            check=False,
        )

        output_last_message = (
            output_last_message_path.read_text(encoding="utf-8")
            if output_last_message_path.exists()
            else ""
        )
        if isinstance(proc.args, (list, tuple)):
            normalized_args = [str(item) for item in proc.args]
        else:
            normalized_args = [str(proc.args)]

        return CodexExecResult(
            args=normalized_args,
            returncode=int(proc.returncode),
            stdout=proc.stdout or "",
            stderr=proc.stderr or "",
            output_last_message=output_last_message,
        )
