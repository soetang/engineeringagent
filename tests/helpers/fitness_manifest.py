from __future__ import annotations

from pathlib import Path

import yaml


def write_shell_contract_manifest(tmp_path: Path) -> Path:
    """Write a minimal shell-contract manifest fixture to disk."""
    command = (
        "print("
        '\'{"contract_version":"1.0","rule_id":"custom.shell-contract","status":"pass",'
        '"severity":"warning","summary":"ok","violations":[]}\')'
    )
    payload = {
        "contract_version": "1.0",
        "rules": [
            {
                "rule_id": "custom.shell-contract",
                "name": "Custom shell contract",
                "summary": "Verify custom command envelope format.",
                "rationale": "Keeps custom adapters interoperable.",
                "remediation": "Update custom command output to the contract.",
                "scope": "harness/fitness_functions",
                "severity": "warning",
                "side_effect_free": True,
                "adapter": "command",
                "config_file": "policies/custom_shell_contract.yaml",
                "command": ["python", "-c", command],
            }
        ],
    }

    manifest_path = tmp_path / "harness" / "fitness_functions" / "rules.yaml"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return manifest_path
