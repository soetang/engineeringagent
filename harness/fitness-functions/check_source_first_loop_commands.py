from __future__ import annotations

import shlex
from pathlib import Path

import yaml

from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.source-first-loop-command-policy"
FEATURES_ROOT = Path("docs/spec/features")
GATES_PATH = Path("harness/gates.yaml")
REMEDIATION = (
    "replace with source-first workspace execution; prefer "
    "`uv run python -m engineeringagent.cli ...`."
)


def _tokenize_command(command: object) -> list[str]:
    if isinstance(command, str):
        try:
            return shlex.split(command)
        except ValueError:
            return command.split()
    if isinstance(command, list):
        return [str(token) for token in command]
    return []


def _command_targets_engineeringagent(tokens: list[str]) -> bool:
    for index, token in enumerate(tokens[1:], start=1):
        if token in {"engineeringagent", "engineeringagent.cli"}:
            return True
        if token.startswith("engineeringagent"):
            return True
        if token == "-m" and index + 1 < len(tokens):
            if tokens[index + 1] == "engineeringagent.cli":
                return True
    return False


def _is_forbidden_uvx_self_invocation(command: object) -> bool:
    tokens = _tokenize_command(command)
    if not tokens:
        return False

    executable_name = Path(tokens[0]).name
    if executable_name != "uvx":
        return False

    has_from_dot = False
    index = 1
    while index < len(tokens):
        token = tokens[index]
        if token == "--from" and index + 1 < len(tokens):
            has_from_dot = has_from_dot or tokens[index + 1] == "."
            index += 2
            continue
        if token.startswith("--from="):
            has_from_dot = has_from_dot or token.split("=", 1)[1] == "."
        index += 1

    return has_from_dot and _command_targets_engineeringagent(tokens)


def _format_command(command: object) -> str:
    if isinstance(command, str):
        return command
    if isinstance(command, list):
        return " ".join(str(token) for token in command)
    return ""


def _scan_feature_verification_commands() -> list[str]:
    if not FEATURES_ROOT.is_dir():
        return []

    violations: list[str] = []
    for feature_path in sorted(FEATURES_ROOT.glob("*.yaml")):
        document = yaml.safe_load(feature_path.read_text(encoding="utf-8")) or {}
        if not isinstance(document, dict):
            continue

        subtasks = document.get("subtasks")
        if not isinstance(subtasks, list):
            continue

        for subtask_index, subtask in enumerate(subtasks):
            if not isinstance(subtask, dict):
                continue
            verification = subtask.get("verification")
            if not isinstance(verification, list):
                continue

            for command_index, command in enumerate(verification):
                if not _is_forbidden_uvx_self_invocation(command):
                    continue
                rendered_command = _format_command(command)
                violations.append(
                    (
                        f"{feature_path.as_posix()}:subtasks[{subtask_index}]"
                        f".verification[{command_index}] forbidden in-repo uvx "
                        f"self-invocation `{rendered_command}`; {REMEDIATION}"
                    )
                )
    return violations


def _scan_gate_commands() -> list[str]:
    if not GATES_PATH.is_file():
        return []

    document = yaml.safe_load(GATES_PATH.read_text(encoding="utf-8")) or {}
    gates = document.get("gates") if isinstance(document, dict) else None
    if not isinstance(gates, dict):
        return []

    violations: list[str] = []
    for gate_id in sorted(gates):
        gate = gates[gate_id]
        if not isinstance(gate, dict):
            continue

        run_command = gate.get("run")
        if _is_forbidden_uvx_self_invocation(run_command):
            violations.append(
                (
                    f"{GATES_PATH.as_posix()}:gates.{gate_id}.run forbidden "
                    f"in-repo uvx self-invocation `{_format_command(run_command)}`; "
                    f"{REMEDIATION}"
                )
            )

        runner = gate.get("runner")
        if not isinstance(runner, dict):
            continue
        runner_command = runner.get("command")
        if _is_forbidden_uvx_self_invocation(runner_command):
            violations.append(
                (
                    f"{GATES_PATH.as_posix()}:gates.{gate_id}.runner.command "
                    "forbidden in-repo uvx self-invocation "
                    f"`{_format_command(runner_command)}`; {REMEDIATION}"
                )
            )

    return violations


def main() -> int:
    """Check scoped loop commands for forbidden in-repo uvx self-invocation."""
    violations = sorted(
        set(_scan_feature_verification_commands() + _scan_gate_commands())
    )
    status = "pass" if not violations else "fail"
    summary = (
        "All scoped loop commands use source-first workspace execution forms."
        if status == "pass"
        else (
            "Detected forbidden in-repo uvx self-invocation patterns in loop command "
            "surfaces."
        )
    )

    emit_result_envelope(
        rule_id=RULE_ID,
        status=status,
        severity="error",
        summary=summary,
        violations=violations,
    )
    return 0 if status == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
