from __future__ import annotations

import sys
from pathlib import Path

import yaml

from engineeringagent.checks.fitness.adapters import execute_rule_definition
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleMetadata,
    RuleAdapter,
    RuleSeverity,
    RuleSource,
    RuleStatus,
)
from engineeringagent.checks.fitness.registry import FitnessRuleDefinition


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


def _write_file(project_root: Path, relative_path: str, body: str) -> None:
    path = project_root / relative_path
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


def _write_prompt_templates(project_root: Path) -> None:
    template_root = project_root / "src" / "engineeringagent" / "prompts" / "templates"
    template_root.mkdir(parents=True, exist_ok=True)
    (template_root / "loop_selector.md").write_text("selector", encoding="utf-8")
    (template_root / "loop_implementation.md").write_text(
        "implementation", encoding="utf-8"
    )
    (template_root / "loop_feedback.md").write_text("feedback", encoding="utf-8")


def _write_scaffold_templates(project_root: Path) -> None:
    template_root = project_root / "src" / "engineeringagent" / "scaffold_templates"
    template_root.mkdir(parents=True, exist_ok=True)
    (template_root / "AGENTS.md").write_text("Agent operating guide", encoding="utf-8")
    (template_root / "precommit.core.yaml").write_text("repos:\n", encoding="utf-8")
    (template_root / "precommit.python_uv.yaml").write_text(
        "repos:\n", encoding="utf-8"
    )
    (template_root / "reference.workflow.md").write_text(
        "Loop workflow", encoding="utf-8"
    )
    (template_root / "reference.contributor-commands.md").write_text(
        "Development practices", encoding="utf-8"
    )
    (template_root / "reference.documentation-practices.md").write_text(
        "Documentation Architecture Reference", encoding="utf-8"
    )


def _fitness_script(repo_root: Path, filename: str) -> Path:
    return repo_root / "harness" / "fitness-functions" / filename


def _non_ignorable_metadata(rule_id: str) -> FitnessRuleMetadata:
    return FitnessRuleMetadata(
        rule_id=rule_id,
        name="No non-ignorable Ruff suppressions",
        summary="Block configured Ruff suppressions.",
        rationale="High-value lint suppressions must be refactor-first.",
        remediation="Remove suppression directives and refactor.",
        scope="src tests harness",
        severity=RuleSeverity.ERROR,
        adapter=RuleAdapter.COMMAND,
        source=RuleSource.CUSTOM,
        side_effect_free=True,
    )


def _non_ignorable_definition(
    script: Path,
    *,
    rule_id: str,
    config_file: Path,
) -> FitnessRuleDefinition:
    return FitnessRuleDefinition(
        metadata=_non_ignorable_metadata(rule_id),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(sys.executable, str(script)),
        config_file=config_file,
    )


def _non_ignorable_cli_definition(script: Path, *argv: str) -> FitnessRuleDefinition:
    rule_id = "custom.no-non-ignorable-ruff-suppressions"
    return FitnessRuleDefinition(
        metadata=_non_ignorable_metadata(rule_id),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(sys.executable, str(script), "--rule-id", rule_id, *argv),
    )


def _write_non_ignorable_policy(
    tmp_path: Path,
    *,
    rule_id: str | None = None,
    blocked_rule_ids: tuple[str, ...] | None = None,
    scan_roots: tuple[str, ...] | None = None,
) -> Path:
    policy_file = tmp_path / "policies" / "no_non_ignorable_ruff_suppressions.yaml"
    policy_file.parent.mkdir(parents=True, exist_ok=True)

    payload: dict[str, object] = {}
    if rule_id is not None:
        payload["rule_id"] = rule_id
    if blocked_rule_ids is not None:
        payload["blocked_rule_ids"] = list(blocked_rule_ids)
    if scan_roots is not None:
        payload["scan_roots"] = list(scan_roots)

    policy_file.write_text(
        yaml.safe_dump(payload, sort_keys=False, allow_unicode=False),
        encoding="utf-8",
    )
    return policy_file


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


def test_execute_rule_definition_appends_config_file_for_command_adapter(
    tmp_path: Path,
) -> None:
    """Append --config-file to command adapters when a rule definition sets one."""
    config_file = tmp_path / "policy.yaml"
    config_file.write_text("policy: test\n", encoding="utf-8")

    rule_script = tmp_path / "rule_with_config.py"
    rule_script.write_text(
        "\n".join(
            [
                "import argparse",
                "import json",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--config-file', required=True)",
                "args = parser.parse_args()",
                "print(json.dumps({",
                f"    'contract_version': '{CONTRACT_VERSION}',",
                "    'rule_id': 'custom.adapter-pass',",
                "    'status': 'pass',",
                "    'severity': 'warning',",
                "    'summary': 'Config file received.',",
                "    'violations': [],",
                "    'details': {'config_file': args.config_file},",
                "}))",
            ]
        ),
        encoding="utf-8",
    )

    definition = _command_definition((sys.executable, str(rule_script))).model_copy(
        update={"config_file": config_file}
    )
    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.PASS
    assert result.details == {"config_file": str(config_file)}


def test_execute_rule_definition_omits_config_file_when_not_configured(
    tmp_path: Path,
) -> None:
    """Do not append --config-file for command adapters without config_file."""
    rule_script = tmp_path / "rule_without_config.py"
    rule_script.write_text(
        "\n".join(
            [
                "import argparse",
                "import json",
                "parser = argparse.ArgumentParser()",
                "parser.add_argument('--config-file')",
                "args = parser.parse_args()",
                "if args.config_file is not None:",
                "    raise SystemExit('unexpected --config-file argument')",
                "print(json.dumps({",
                f"    'contract_version': '{CONTRACT_VERSION}',",
                "    'rule_id': 'custom.adapter-pass',",
                "    'status': 'pass',",
                "    'severity': 'warning',",
                "    'summary': 'No config file argument received.',",
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
    repo_root: Path,
) -> None:
    """Load Ruff suppression policy from --config-file and surface fail status."""
    scan_root = tmp_path / "src"
    scan_root.mkdir(parents=True)
    target = scan_root / "module.py"
    target.write_text(
        "def run(a, b, c, d, e, f):  # noqa: PLR0913\n    return a + b\n",
        encoding="utf-8",
    )
    policy_file = _write_non_ignorable_policy(
        tmp_path,
        rule_id="custom.no-non-ignorable-ruff-suppressions",
        blocked_rule_ids=("PLR0913",),
        scan_roots=("src",),
    )

    script = _fitness_script(repo_root, "check_non_ignorable_ruff_suppressions.py")

    definition = _non_ignorable_definition(
        script,
        rule_id="custom.no-non-ignorable-ruff-suppressions",
        config_file=policy_file,
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert result.severity == RuleSeverity.ERROR
    assert result.violations


def test_non_ignorable_suppression_adapter_surfaces_yaml_parse_errors(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Return structured policy-configuration errors for malformed YAML."""
    policy_file = tmp_path / "policies" / "no_non_ignorable_ruff_suppressions.yaml"
    policy_file.parent.mkdir(parents=True, exist_ok=True)
    policy_file.write_text("rule_id: bad: yaml\n", encoding="utf-8")

    script = _fitness_script(repo_root, "check_non_ignorable_ruff_suppressions.py")

    definition = _non_ignorable_definition(
        script,
        rule_id="architecture.no-non-ignorable-ruff-suppressions",
        config_file=policy_file,
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.ERROR
    assert result.summary.startswith(
        "Invalid Ruff suppression policy configuration: unable to parse config file"
    )
    assert result.violations == []


def test_non_ignorable_suppression_adapter_surfaces_missing_blocked_ids_error(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Keep config validation errors visible when policy defines a custom rule_id."""
    policy_file = _write_non_ignorable_policy(
        tmp_path,
        rule_id="custom.no-non-ignorable-ruff-suppressions",
        scan_roots=("src",),
    )

    script = _fitness_script(repo_root, "check_non_ignorable_ruff_suppressions.py")

    definition = _non_ignorable_definition(
        script,
        rule_id="custom.no-non-ignorable-ruff-suppressions",
        config_file=policy_file,
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.rule_id == "custom.no-non-ignorable-ruff-suppressions"
    assert result.status == RuleStatus.ERROR
    assert result.summary.startswith(
        "Invalid Ruff suppression policy configuration: missing blocked rule IDs"
    )
    assert result.violations == []


def test_non_ignorable_suppression_adapter_honors_explicit_scan_roots(
    tmp_path: Path,
    repo_root: Path,
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

    script = _fitness_script(repo_root, "check_non_ignorable_ruff_suppressions.py")

    definition = _non_ignorable_cli_definition(
        script,
        "--blocked-rule-id",
        "PLR0913",
        "--scan-root",
        "src",
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.PASS
    assert not result.violations


def test_non_ignorable_suppression_adapter_detects_file_level_and_multicode_noqa(
    tmp_path: Path,
    repo_root: Path,
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

    script = _fitness_script(repo_root, "check_non_ignorable_ruff_suppressions.py")

    definition = _non_ignorable_cli_definition(
        script,
        "--blocked-rule-id",
        "D103",
        "--blocked-rule-id",
        "PLR0913",
        "--scan-root",
        "src",
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert len(result.violations) == 2
    assert "src/a_module.py:1:1" in result.violations[0]
    assert "targets: D103" in result.violations[0]
    assert "src/z_module.py:1:29" in result.violations[1]
    assert "targets: PLR0913" in result.violations[1]
    assert "NamedTuple or pydantic model" in result.violations[1]


def test_execute_rule_definition_runs_loop_subprocess_boundary_adapter(
    tmp_path: Path,
) -> None:
    """Execute the command adapter without invoking semgrep-backed scripts."""
    rule_script = tmp_path / "rule.py"
    rule_script.write_text(
        "\n".join(
            [
                "import json",
                "import os",
                "print(json.dumps({",
                f"    'contract_version': '{CONTRACT_VERSION}',",
                "    'rule_id': 'architecture.loop-subprocess-boundary',",
                "    'status': 'fail',",
                "    'severity': 'error',",
                "    'summary': 'Detected subprocess invocation(s) outside allowlisted modules.',",
                "    'violations': [f'cwd={os.getcwd()}'],",
                "}))",
            ]
        ),
        encoding="utf-8",
    )

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="architecture.loop-subprocess-boundary",
            name="Loop subprocess boundary",
            summary="Enforce subprocess allowlist boundaries for command adapters/clients.",
            rationale="Centralizes command execution paths for consistent control.",
            remediation=(
                "Move OpenCode command execution to engineeringagent.opencode.client "
                "and Git command execution to engineeringagent.git.client."
            ),
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(
            sys.executable,
            str(rule_script),
        ),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert result.severity == RuleSeverity.ERROR
    assert result.violations == [f"cwd={tmp_path}"]


def test_execute_rule_definition_runs_dependency_directionality_adapter(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Surface fail status from the migrated dependency-directionality adapter."""
    _write_file(tmp_path, "src/engineeringagent/cli.py", "")
    _write_file(tmp_path, "src/engineeringagent/loop.py", "")
    _write_file(tmp_path, "src/engineeringagent/gates.py", "")
    _write_file(
        tmp_path,
        "src/engineeringagent/validator.py",
        "from .specs import FeatureSpec\n",
    )
    _write_file(
        tmp_path, "src/engineeringagent/specs.py", "import engineeringagent.loop\n"
    )

    script = _fitness_script(repo_root, "check_dependency_directionality.py")

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="architecture.dep-directionality",
            name="Dependency directionality",
            summary="Enforce dependency directionality boundaries.",
            rationale="Core modules must preserve dependency layering constraints.",
            remediation=(
                "Remove blocked imports from protected modules to restore "
                "dependency directionality."
            ),
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(
            sys.executable,
            str(script),
        ),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert result.severity == RuleSeverity.ERROR
    assert any(
        "engineeringagent.specs imports blocked dependency engineeringagent.loop"
        in violation
        for violation in result.violations
    )


def test_execute_rule_definition_runs_prompt_locality_adapter(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Surface fail status from the migrated prompt-locality adapter."""
    _write_prompt_templates(tmp_path)
    _write_file(
        tmp_path,
        "src/engineeringagent/loop.py",
        "PROMPT = 'Read... and use this feature spec from disk!!!'\n",
    )

    script = _fitness_script(repo_root, "check_prompt_locality.py")

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="architecture.prompt-locality",
            name="Prompt locality",
            summary="Enforce canonical prompt locality boundaries.",
            rationale="Canonical prompt content must stay in approved prompt assets.",
            remediation=(
                "Move canonical prompt text and template reads into "
                "src/engineeringagent/prompts/templates and approved modules under "
                "src/engineeringagent/prompts/."
            ),
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(
            sys.executable,
            str(script),
        ),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert result.severity == RuleSeverity.ERROR
    assert any(
        "src/engineeringagent/loop.py:1 contains canonical prompt canary "
        "'read and use this feature spec from disk'" in violation
        for violation in result.violations
    )


def test_execute_rule_definition_runs_scaffold_template_locality_adapter(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Surface fail status from the migrated scaffold-template-locality adapter."""
    _write_scaffold_templates(tmp_path)
    _write_file(
        tmp_path,
        "src/engineeringagent/loop.py",
        "SCAFFOLD = 'Agent operating guide for this repository.'\n",
    )

    script = _fitness_script(repo_root, "check_scaffold_template_locality.py")

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="architecture.scaffold-template-locality",
            name="Scaffold template locality",
            summary="Enforce scaffold template locality boundaries.",
            rationale="Scaffold template content must stay in scaffold template assets.",
            remediation=(
                "Move scaffold template content into "
                "src/engineeringagent/scaffold_templates and keep scaffold content "
                "reads inside engineeringagent.init_scaffold."
            ),
            scope="src/engineeringagent",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(
            sys.executable,
            str(script),
        ),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert result.severity == RuleSeverity.ERROR
    assert any(
        "src/engineeringagent/loop.py:1 contains scaffold template canary "
        "'agent operating guide for this repository'" in violation
        for violation in result.violations
    )


def test_execute_rule_definition_runs_markdown_locality_reference_adapter(
    tmp_path: Path,
    repo_root: Path,
) -> None:
    """Surface fail status from the migrated markdown locality adapter."""
    _write_file(tmp_path, "README.md", "Root readme\n")

    script = _fitness_script(repo_root, "check_markdown_locality_reference_coverage.py")

    definition = FitnessRuleDefinition(
        metadata=FitnessRuleMetadata(
            rule_id="architecture.markdown-locality-reference-coverage",
            name="Markdown locality and reference coverage",
            summary="Enforce markdown locality and reference coverage constraints.",
            rationale=(
                "Keeps markdown assets discoverable and ensures non-doc markdown files "
                "remain referenced from in-repo sources."
            ),
            remediation=(
                "Move markdown files into approved roots and add deterministic "
                "in-repo references for non-doc markdown files."
            ),
            scope="repository",
            severity=RuleSeverity.ERROR,
            adapter=RuleAdapter.COMMAND,
            source=RuleSource.CUSTOM,
            side_effect_free=True,
        ),
        origin="custom:harness/fitness-functions/rules.yaml:rules[0]",
        command=(
            sys.executable,
            str(script),
        ),
    )

    result = execute_rule_definition(definition, project_root=tmp_path)

    assert result.status == RuleStatus.FAIL
    assert result.severity == RuleSeverity.ERROR
    assert any(
        "README.md:1 markdown file outside docs/ has no in-repo non-self reference"
        in violation
        for violation in result.violations
    )


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
