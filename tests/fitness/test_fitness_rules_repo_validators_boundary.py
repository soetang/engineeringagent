from pathlib import Path

import yaml


def test_repo_validators_boundary_fitness_rule_not_registered() -> None:
    """Manifest must not include the removed repo validators boundary rule."""
    manifest_path = Path("harness/fitness_functions/rules.yaml")
    manifest = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    assert isinstance(manifest, dict)

    rules = manifest.get("rules")
    assert isinstance(rules, list)

    matching = [
        rule
        for rule in rules
        if isinstance(rule, dict)
        and rule.get("rule_id") == "architecture.repo-validators-boundary"
    ]
    assert not matching


def test_repo_validators_boundary_checker_removed() -> None:
    """Removed rule checker script should not remain in harness."""
    assert not Path(
        "harness/fitness_functions/check_repo_validators_boundary.py"
    ).exists()
