from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml

from .specs import gate_contract_issues, load_yaml


DEFAULT_GATE_CONFIG: dict[str, Any] = {
    "profiles": {
        "precommit": [
            "yaml_validate",
            "spec_validate",
            "ruff_validate",
            "pytest_validate",
        ],
        "loop_fast": ["spec_validate", "opencode_permission_probe"],
    },
    "gates": {
        "yaml_validate": {"run": "uv run python harness/validate_yaml.py"},
        "spec_validate": {"run": "uvx --from . engineeringagent validate"},
        "ruff_validate": {"run": "uv run ruff check src/engineeringagent"},
        "pytest_validate": {"run": "uv run pytest -q"},
        "opencode_permission_probe": {
            "run": "uv run python harness/permission_probe.py"
        },
    },
}


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
    return data


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
    config: dict[str, Any], profile: str, cwd: Path
) -> tuple[bool, str | None]:
    """Execute gates in a profile in declaration order.

    Args:
        config: Parsed gate configuration mapping.
        profile: Profile name to run.
        cwd: Working directory used for gate commands.

    Returns:
        Tuple of success flag and failed gate name when any command fails.

    Raises:
        ValueError: If profile is unknown or a gate has no run command.
    """
    profiles = config.get("profiles", {})
    gates = config.get("gates", {})
    if profile not in profiles:
        raise ValueError(f"unknown profile: {profile}")

    for gate_name in profiles[profile]:
        gate = gates.get(gate_name, {})
        command = gate.get("run")
        if not command:
            raise ValueError(f"gate '{gate_name}' has no run command")
        proc = subprocess.run(command, cwd=cwd, shell=True)
        if proc.returncode != 0:
            return (False, gate_name)
    return (True, None)
