from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Any

import yaml


def load_gate_config(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    if not isinstance(data, dict):
        raise ValueError("gates config must be a mapping")
    return data


def list_profiles(config: dict[str, Any]) -> list[str]:
    profiles = config.get("profiles", {})
    if not isinstance(profiles, dict):
        return []
    return sorted(profiles.keys())


def run_profile(config: dict[str, Any], profile: str, cwd: Path) -> tuple[bool, str | None]:
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
