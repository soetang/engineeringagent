from __future__ import annotations

from pathlib import Path

import yaml

from tests.cli.init_command_support import invoke_cli


def test_init_slim_pack_does_not_scaffold_demo_failure(tmp_path: Path) -> None:
    """Verify slim pack scaffolds validations without demo failing rule wiring."""
    result = invoke_cli(["--project-root", str(tmp_path), "init", "slim"])

    assert result.exit_code == 0
    assert "pack=slim" in result.stdout
    assert not (tmp_path / "harness" / "gates.yaml").exists()
    assert not (tmp_path / "harness" / "reviewers.yaml").exists()
    assert not (
        tmp_path / "harness" / "fitness_functions" / "demo_always_fail.py"
    ).exists()

    checks_config = yaml.safe_load(
        (tmp_path / "harness" / "checks.yaml").read_text(encoding="utf-8")
    )
    assert checks_config["contract_version"] == "1.0"
    assert checks_config["groups"] == []
    assert checks_config["checks"] == {}


def test_init_standard_pack_scaffolds_demo_failing_fitness_rule(
    tmp_path: Path,
) -> None:
    """Verify standard pack wires an always-failing demo fitness rule."""
    result = invoke_cli(["--project-root", str(tmp_path), "init", "standard"])

    assert result.exit_code == 0
    assert "pack=standard" in result.stdout
    assert "demo failing" in result.stdout.lower()
    assert not (tmp_path / "harness" / "gates.yaml").exists()
    assert not (tmp_path / "harness" / "reviewers.yaml").exists()

    demo_script_path = (
        tmp_path / "harness" / "fitness_functions" / "demo_always_fail.py"
    )
    assert demo_script_path.exists()

    baseline_manifest = yaml.safe_load(
        (tmp_path / "harness" / "fitness_functions" / "rules.yaml").read_text(
            encoding="utf-8"
        )
    )
    assert baseline_manifest["contract_version"] == "1.0"
    assert [rule["rule_id"] for rule in baseline_manifest["rules"]] == [
        "demo.always-fail"
    ]

    checks_config = yaml.safe_load(
        (tmp_path / "harness" / "checks.yaml").read_text(encoding="utf-8")
    )
    assert checks_config["contract_version"] == "1.0"
    assert checks_config["groups"] == [
        {
            "group_id": "fitness",
            "description": "Run all configured fitness functions.",
            "checks": ["fitness_all"],
        }
    ]
    assert checks_config["checks"]["fitness_all"]["type"] == "fitness"
