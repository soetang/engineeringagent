from __future__ import annotations

from pathlib import Path
import sys

from engineeringagent.fitness.adapters import execute_rule_definition
from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
    RuleStatus,
)
from engineeringagent.fitness.registry import FitnessRuleDefinition


def _command_definition(command: tuple[str, ...]) -> FitnessRuleDefinition:
    return FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="custom.adapter-pass",
            name="Custom adapter pass",
            summary="Validate command adapter result parsing.",
            rationale="Custom rules need a stable execution contract.",
            remediation="Fix the external rule command output envelope.",
            scope="harness/fitness-functions/rules.yaml",
            severity=RuleSeverity.WARNING,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=command,
    )


def test_execute_rule_definition_runs_command_adapter_with_json_envelope(
    tmp_path: Path,
) -> None:
    """Return validated command-adapter result payloads."""
    rule_script = tmp_path / "rule.py"
    rule_script.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({",
                f"    'contract_version': '{CONTRACT_VERSION}',",
                "    'rule_id': 'custom.adapter-pass',",
                "    'status': 'pass',",
                "    'severity': 'warning',",
                "    'summary': 'All checks passed.',",
                "    'violations': [],",
                "}))",
            ]
        ),
        encoding="utf-8",
    )

    result = execute_rule_definition(
        _command_definition((sys.executable, str(rule_script))),
        project_root=tmp_path,
    )

    assert result.status == RuleStatus.PASS
    assert result.rule_id == "custom.adapter-pass"


def test_execute_rule_definition_runs_python_adapter_callable(tmp_path: Path) -> None:
    """Execute built-in Python adapter callables through a shared runner."""

    def _rule_callable(project_root: Path) -> dict[str, object]:
        assert project_root == tmp_path
        return {
            "contract_version": CONTRACT_VERSION,
            "rule_id": "builtin.python-adapter",
            "status": "pass",
            "severity": "error",
            "summary": "Built-in Python adapter ran.",
            "violations": [],
        }

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="builtin.python-adapter",
            name="Built-in python adapter",
            summary="Validate Python adapter dispatch.",
            rationale="Built-in rules run natively in Python.",
            remediation="Provide a valid Python fitness callable.",
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.PYTHON,
            source=RuleSource.BUILTIN,
            side_effect_free=True,
        ),
        origin="builtin:builtin.python-adapter",
        python_callable=_rule_callable,
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.PASS
    assert result.rule_id == "builtin.python-adapter"


def test_execute_rule_definition_runs_non_ignorable_suppression_adapter(
    tmp_path: Path,
) -> None:
    """Surface fail status from the Ruff suppression adapter envelope."""
    scan_root = tmp_path / "src"
    scan_root.mkdir(parents=True)
    target = scan_root / "module.py"
    target.write_text(
        "def run(a, b, c, d, e, f):  # noqa: PLR0913\n    return a + b\n",
        encoding="utf-8",
    )

    script = Path(__file__).resolve().parents[1] / "harness" / "fitness-functions"
    script = script / "check_non_ignorable_ruff_suppressions.py"

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="custom.no-non-ignorable-ruff-suppressions",
            name="No non-ignorable Ruff suppressions",
            summary="Block configured Ruff suppressions.",
            rationale="High-value lint suppressions must be refactor-first.",
            remediation="Remove suppression directives and refactor.",
            scope="src tests harness",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(
            sys.executable,
            str(script),
            "--rule-id",
            "custom.no-non-ignorable-ruff-suppressions",
            "--blocked-rule-id",
            "PLR0913",
            "--scan-root",
            "src",
        ),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert result.severity == RuleSeverity.ERROR
    assert result.violations


def test_non_ignorable_suppression_adapter_honors_explicit_scan_roots(
    tmp_path: Path,
) -> None:
    """Only scan explicitly configured roots when --scan-root is provided."""
    src_root = tmp_path / "src"
    src_root.mkdir(parents=True)
    (src_root / "module.py").write_text(
        "def run() -> int:\n    return 1\n", encoding="utf-8"
    )

    harness_root = tmp_path / "harness"
    harness_root.mkdir(parents=True)
    (harness_root / "blocked.py").write_text(
        "def run(a, b, c, d, e, f):  # noqa: PLR0913\n    return a + b\n",
        encoding="utf-8",
    )

    script = Path(__file__).resolve().parents[1] / "harness" / "fitness-functions"
    script = script / "check_non_ignorable_ruff_suppressions.py"

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="custom.no-non-ignorable-ruff-suppressions",
            name="No non-ignorable Ruff suppressions",
            summary="Block configured Ruff suppressions.",
            rationale="High-value lint suppressions must be refactor-first.",
            remediation="Remove suppression directives and refactor.",
            scope="src tests harness",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(
            sys.executable,
            str(script),
            "--rule-id",
            "custom.no-non-ignorable-ruff-suppressions",
            "--blocked-rule-id",
            "PLR0913",
            "--scan-root",
            "src",
        ),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.PASS
    assert result.violations == []


def test_non_ignorable_suppression_adapter_detects_file_level_and_multicode_noqa(
    tmp_path: Path,
) -> None:
    """Detect file-level and inline multi-code suppressions deterministically."""
    src_root = tmp_path / "src"
    src_root.mkdir(parents=True)
    (src_root / "z_module.py").write_text(
        "def run(a, b, c, d, e, f):  # noqa: F401, PLR0913\n    return a + b\n",
        encoding="utf-8",
    )
    (src_root / "a_module.py").write_text(
        "# ruff: noqa: D103\n\ndef run() -> int:\n    return 1\n",
        encoding="utf-8",
    )

    script = Path(__file__).resolve().parents[1] / "harness" / "fitness-functions"
    script = script / "check_non_ignorable_ruff_suppressions.py"

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="custom.no-non-ignorable-ruff-suppressions",
            name="No non-ignorable Ruff suppressions",
            summary="Block configured Ruff suppressions.",
            rationale="High-value lint suppressions must be refactor-first.",
            remediation="Remove suppression directives and refactor.",
            scope="src tests harness",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(
            sys.executable,
            str(script),
            "--rule-id",
            "custom.no-non-ignorable-ruff-suppressions",
            "--blocked-rule-id",
            "D103",
            "--blocked-rule-id",
            "PLR0913",
            "--scan-root",
            "src",
        ),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert len(result.violations) == 2
    assert "src/a_module.py:1:1" in result.violations[0]
    assert "targets: D103" in result.violations[0]
    assert "src/z_module.py:1:29" in result.violations[1]
    assert "targets: PLR0913" in result.violations[1]
    assert "NamedTuple or pydantic model" in result.violations[1]


def test_execute_rule_definition_rejects_extra_result_fields(tmp_path: Path) -> None:
    """Reject command envelopes that drift from the result contract."""
    rule_script = tmp_path / "rule.py"
    rule_script.write_text(
        "\n".join(
            [
                "import json",
                "print(json.dumps({",
                f"    'contract_version': '{CONTRACT_VERSION}',",
                "    'rule_id': 'custom.adapter-pass',",
                "    'status': 'pass',",
                "    'severity': 'warning',",
                "    'summary': 'All checks passed.',",
                "    'violations': [],",
                "    'unexpected': 'contract drift',",
                "}))",
            ]
        ),
        encoding="utf-8",
    )

    result = execute_rule_definition(
        _command_definition((sys.executable, str(rule_script))),
        project_root=tmp_path,
    )

    assert result.status == RuleStatus.ERROR
    assert result.rule_id == "custom.adapter-pass"
    assert result.summary.startswith("Adapter execution failed:")
