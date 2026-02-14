from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml
from pydantic import BaseModel, ConfigDict

from .on_change_matcher import path_matches_any_glob
from .specs import gate_contract_issues, load_yaml


DEFAULT_GATE_CONFIG: dict[str, Any] = {
    "contract_version": "1.0",
    "profiles": {
        "precommit": [
            "yaml_validate",
            "spec_validate",
            "fitness_validate",
            "mdformat_validate",
            "ruff_validate",
            "pyright_validate",
            "pytest_validate",
        ],
        "loop_fast": [
            "spec_validate",
            "fitness_validate",
        ],
    },
    "gates": {
        "yaml_validate": {"run": "uv run python harness/validate_yaml.py"},
        "spec_validate": {
            "run": "uv run python -m engineeringagent.cli validate",
            "on_change": [
                "docs/spec/**/*.yaml",
                "docs/spec/**/*.yml",
                "docs/spec/**/*.json",
            ],
        },
        "fitness_validate": {
            "run": "uv run python -m engineeringagent.cli fitness run --format json"
        },
        "mdformat_validate": {
            "run": "uv run mdformat --check README.md AGENTS.md docs/references/docs-architecture-llms.md"
        },
        "ruff_validate": {
            "run": "uv run ruff check src/engineeringagent",
            "on_change": [
                "src/**/*.py",
                "tests/**/*.py",
                "harness/**/*.py",
            ],
        },
        "pyright_validate": {
            "run": "uv run pyright src/engineeringagent tests harness",
            "on_change": [
                "src/**/*.py",
                "tests/**/*.py",
                "harness/**/*.py",
            ],
        },
        "pytest_validate": {
            "run": "uv run pytest -q",
            "on_change": [
                "src/**/*.py",
                "tests/**/*.py",
                "harness/**/*.py",
            ],
        },
        "opencode_permission_probe": {
            "run": "uv run python harness/permission_probe.py"
        },
    },
}


FALLBACK_CHANGE_DISCOVERY_REASON = "fallback_run_all_change_discovery_failed"
ALWAYS_RUN_NO_ON_CHANGE_REASON = "always_run_no_on_change"
MATCHED_ON_CHANGE_REASON = "matched_on_change"
NO_ON_CHANGE_MATCH_REASON = "no_on_change_match"


class ChangedPathsResult(BaseModel):
    """Deterministic changed-path discovery result for gate planning."""

    model_config = ConfigDict(frozen=True, extra="forbid")

    paths: tuple[str, ...]
    run_all: bool
    reason: str | None


def plan_profile(
    config: dict[str, Any],
    profile: str,
    *,
    changed_paths: ChangedPathsResult,
) -> list[dict[str, str]]:
    """Plan deterministic gate run/skip decisions for one profile.

    Args:
        config: Parsed gate configuration mapping.
        profile: Profile name to evaluate.
        changed_paths: Resolved changed-paths input and fallback metadata.

    Returns:
        Ordered list of gate decision envelopes.

    Raises:
        ValueError: If profile is unknown.
    """
    profiles = config.get("profiles", {})
    gates = config.get("gates", {})
    if profile not in profiles:
        raise ValueError(f"unknown profile: {profile}")

    fallback_reason = changed_paths.reason or FALLBACK_CHANGE_DISCOVERY_REASON
    decisions: list[dict[str, str]] = []
    for gate_name in profiles[profile]:
        gate = gates.get(gate_name, {})
        on_change = gate.get("on_change")

        if changed_paths.run_all:
            decisions.append(
                {
                    "gate": gate_name,
                    "decision": "run",
                    "reason": fallback_reason,
                }
            )
            continue

        if on_change is None:
            decisions.append(
                {
                    "gate": gate_name,
                    "decision": "run",
                    "reason": ALWAYS_RUN_NO_ON_CHANGE_REASON,
                }
            )
            continue

        if any(path_matches_any_glob(path, on_change) for path in changed_paths.paths):
            decisions.append(
                {
                    "gate": gate_name,
                    "decision": "run",
                    "reason": MATCHED_ON_CHANGE_REASON,
                }
            )
            continue

        decisions.append(
            {
                "gate": gate_name,
                "decision": "skip",
                "reason": NO_ON_CHANGE_MATCH_REASON,
            }
        )

    return decisions


def collect_changed_paths(
    cwd: Path,
    *,
    base: str | None = None,
    head: str | None = None,
) -> ChangedPathsResult:
    """Collect repository-relative changed paths for gate selection.

    Args:
        cwd: Repository root used for git diff execution.
        base: Optional diff base reference.
        head: Optional diff head reference.

    Returns:
        Deterministic changed-path result with optional fallback metadata.
    """
    command = [
        "git",
        "diff",
        "--name-status",
        "--find-renames",
        "--diff-filter=AMDR",
    ]
    if base is not None:
        command.append(base)
    if head is not None:
        command.append(head)

    proc = subprocess.run(command, cwd=cwd, capture_output=True, text=True)
    if proc.returncode != 0:
        return ChangedPathsResult(
            paths=(),
            run_all=True,
            reason=FALLBACK_CHANGE_DISCOVERY_REASON,
        )

    changed_paths: set[str] = set()
    for line in proc.stdout.splitlines():
        if not line.strip():
            continue
        parts = line.split("\t")
        if len(parts) < 2:
            return ChangedPathsResult(
                paths=(),
                run_all=True,
                reason=FALLBACK_CHANGE_DISCOVERY_REASON,
            )

        status = parts[0]
        if status.startswith("R"):
            if len(parts) < 3:
                return ChangedPathsResult(
                    paths=(),
                    run_all=True,
                    reason=FALLBACK_CHANGE_DISCOVERY_REASON,
                )
            changed_paths.add(parts[1].replace("\\", "/"))
            changed_paths.add(parts[2].replace("\\", "/"))
            continue

        changed_paths.add(parts[1].replace("\\", "/"))

    return ChangedPathsResult(
        paths=tuple(sorted(changed_paths)),
        run_all=False,
        reason=None,
    )


def load_gate_config(path: Path) -> dict[str, Any]:
    """Load gate configuration from disk.

    Args:
        path: Path to the gates YAML file.

    Returns:
        Parsed gate configuration mapping.

    Raises:
        ValueError: If the YAML top level is not a mapping.
    """
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("w", encoding="utf-8") as f:
            yaml.safe_dump(DEFAULT_GATE_CONFIG, f, sort_keys=False)

    data = load_yaml(path)
    contract_issues = gate_contract_issues(data, path)
    if contract_issues:
        formatted = "; ".join(
            f"{issue.path}: {issue.message}" for issue in contract_issues
        )
        raise ValueError(f"invalid gates config: {formatted}")
    config = dict(data)
    config.setdefault("contract_version", "1.0")
    return config


def normalize_gate_runner(gate: dict[str, Any]) -> dict[str, str]:
    """Normalize legacy and structured gate runners into one shape.

    Args:
        gate: Gate definition mapping.

    Returns:
        Normalized runner mapping with type and command keys.

    Raises:
        ValueError: If gate has both runner forms or no runner form.
    """
    run = gate.get("run")
    runner = gate.get("runner")
    has_run = bool(run)
    has_runner = isinstance(runner, dict)

    if has_run and has_runner:
        raise ValueError("gate has both run and runner definitions")
    if not has_run and not has_runner:
        raise ValueError("gate has no run command")
    if has_run:
        return {"type": "command", "command": str(run)}
    assert isinstance(runner, dict)
    return {"type": str(runner["type"]), "command": str(runner["command"])}


def list_profiles(config: dict[str, Any]) -> list[str]:
    """Return sorted profile names from a gate config.

    Args:
        config: Parsed gate configuration mapping.

    Returns:
        Sorted profile names, or an empty list if profiles is invalid.
    """
    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict):
        return []
    return sorted(profiles.keys())


def run_profile(
    config: dict[str, Any],
    profile: str,
    cwd: Path,
    capture_output: bool = False,
    changed_paths: ChangedPathsResult | None = None,
) -> tuple[bool, str | None, str]:
    """Execute gates in a profile in declaration order.

    Args:
        config: Parsed gate configuration mapping.
        profile: Profile name to run.
        cwd: Working directory used for gate commands.
        capture_output: Whether to capture and return gate command output.
        changed_paths: Optional pre-resolved changed paths used for deterministic
            gate planning decisions.

    Returns:
        Tuple of success flag, failed gate name, and combined gate output.

    Raises:
        ValueError: If profile is unknown or a gate has no run command.
    """
    gates = config.get("gates", {})
    planning_input = changed_paths or ChangedPathsResult(
        paths=(),
        run_all=True,
        reason=FALLBACK_CHANGE_DISCOVERY_REASON,
    )
    decisions = plan_profile(config, profile, changed_paths=planning_input)

    combined_output_parts: list[str] = []
    for gate_plan in decisions:
        if gate_plan["decision"] != "run":
            continue

        gate_name = gate_plan["gate"]
        gate = gates.get(gate_name, {})
        try:
            runner = normalize_gate_runner(gate)
        except ValueError as exc:
            if str(exc) == "gate has no run command":
                raise ValueError(f"gate '{gate_name}' has no run command") from exc
            raise ValueError(
                f"gate '{gate_name}' has invalid runner definition"
            ) from exc
        command = runner["command"]

        if capture_output:
            proc = subprocess.run(
                command,
                cwd=cwd,
                shell=True,
                capture_output=True,
                text=True,
            )
            combined_output_parts.append(f"[gate:{gate_name}] command={command}")
            if proc.stdout:
                combined_output_parts.append(proc.stdout.rstrip("\n"))
            if proc.stderr:
                combined_output_parts.append(proc.stderr.rstrip("\n"))
        else:
            proc = subprocess.run(command, cwd=cwd, shell=True)

        if proc.returncode != 0:
            return (False, gate_name, "\n".join(combined_output_parts).strip())
    return (True, None, "\n".join(combined_output_parts).strip())
