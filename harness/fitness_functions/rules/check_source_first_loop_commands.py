from __future__ import annotations

import shlex
from pathlib import Path
import re

import yaml

from engineeringagent.adapters.config import resolve_specifications_root
from engineeringagent.domain.specification import iter_feature_files
from engineeringagent.domain.specification import resolve_feature_plan_path
from engineeringagent.adapters.quality.fitness import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.source-first-loop-command-policy"
CHECKS_PATH = Path("harness/checks.yaml")
SMOKE_PLAN_TEMPLATE_PATH = Path("docs/fixtures/real_opencode_hello_world_plan_template.md")
PLAN_SESSION_APPROACH_PATH = Path("src/engineeringagent/approach/docs/plan-session.md")
RESEARCH_SESSION_APPROACH_PATH = Path("src/engineeringagent/approach/docs/research-session.md")
CONTRIBUTOR_APPROACH_DOC_PATHS = (
    Path("src/engineeringagent/approach/docs/workflow.md"),
    Path("src/engineeringagent/approach/docs/quality-checks.md"),
    Path("src/engineeringagent/approach/docs/reviewer-authoring.md"),
    Path("src/engineeringagent/approach/docs/specifications.md"),
)
LOOP_IMPLEMENTATION_PROMPT_PATH = Path(
    "harness/prompts/implementation_default.py"
)
REMEDIATION = (
    "replace with source-first workspace execution; prefer "
    "`uv run engineeringagent ...` over "
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


def _is_legacy_module_cli_invocation(command: object) -> bool:
    tokens = _tokenize_command(command)
    if not tokens:
        return False

    index = 0
    if len(tokens) >= 2 and Path(tokens[0]).name == "uv" and tokens[1] == "run":
        index = 2

    if index + 2 >= len(tokens):
        return False

    executable_name = Path(tokens[index]).name
    if not executable_name.startswith("python"):
        return False

    return tokens[index + 1] == "-m" and tokens[index + 2] == "engineeringagent.cli"


def _format_command(command: object) -> str:
    if isinstance(command, str):
        return command
    if isinstance(command, list):
        return " ".join(str(token) for token in command)
    return ""


def _command_policy_violation(command: object) -> str | None:
    if _is_forbidden_uvx_self_invocation(command):
        return "forbidden in-repo uvx self-invocation"
    if _is_legacy_module_cli_invocation(command):
        return "legacy module-form engineeringagent invocation"
    return None


def _iter_feature_specs(project_root: Path) -> list[Path]:
    features_root = resolve_specifications_root(project_root) / "features"
    if not features_root.is_dir():
        return []
    return list(iter_feature_files(features_root))


def _load_markdown_frontmatter(path: Path) -> dict[str, object] | None:
    document = path.read_text(encoding="utf-8")
    if not document.startswith("---\n"):
        return None

    frontmatter_end = document.find("\n---", 4)
    if frontmatter_end < 0:
        return None

    frontmatter = yaml.safe_load(document[4:frontmatter_end].strip())
    return frontmatter if isinstance(frontmatter, dict) else None


def _scan_markdown_phase_commands(plan_path: Path) -> list[str]:
    if not plan_path.is_file():
        return []

    frontmatter = _load_markdown_frontmatter(plan_path)
    if not isinstance(frontmatter, dict):
        return []

    phases = frontmatter.get("phases")
    if not isinstance(phases, list):
        return []

    violations: list[str] = []
    for phase_index, phase in enumerate(phases):
        if not isinstance(phase, dict):
            continue
        verification = phase.get("verification")
        if not isinstance(verification, list):
            continue

        for command_index, command in enumerate(verification):
            violation_reason = _command_policy_violation(command)
            if violation_reason is None:
                continue
            rendered_command = _format_command(command)
            violations.append(
                (
                    f"{plan_path.as_posix()}:phases[{phase_index}]"
                    f".verification[{command_index}] {violation_reason} "
                    f"`{rendered_command}`; {REMEDIATION}"
                )
            )
    return violations


def _scan_bundled_plan_phase_commands(
    feature_path: Path,
    document: dict[str, object],
) -> list[str]:
    plan_path = resolve_feature_plan_path(feature_path, document)
    if plan_path is None:
        return []
    return _scan_markdown_phase_commands(plan_path)


def _scan_feature_verification_commands(project_root: Path) -> list[str]:
    violations: list[str] = []
    for feature_path in _iter_feature_specs(project_root):
        document = yaml.safe_load(feature_path.read_text(encoding="utf-8")) or {}
        if not isinstance(document, dict):
            continue
        violations.extend(_scan_bundled_plan_phase_commands(feature_path, document))
    return violations


def _scan_smoke_template_commands() -> list[str]:
    return _scan_markdown_phase_commands(SMOKE_PLAN_TEMPLATE_PATH)


def _scan_markdown_command_lines(path: Path) -> list[str]:
    if not path.is_file():
        return []

    violations: list[str] = []
    for line_number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
        if "engineeringagent" not in line:
            continue
        candidates = [
            segment
            for segment in re.findall(r"`([^`]+)`", line)
            if "engineeringagent" in segment
        ]
        candidates.extend(
            segment
            for quote, segment in re.findall(r"(['\"])(.*?)\1", line)
            if "engineeringagent" in segment
        )
        if not candidates:
            candidates = [line.strip("`- ")]
        for candidate in candidates:
            violation_reason = _command_policy_violation(candidate)
            if violation_reason is None:
                continue
            violations.append(
                (
                    f"{path.as_posix()}:line {line_number} {violation_reason} "
                    f"`{line.strip()}`; {REMEDIATION}"
                )
            )
    return violations


def _scan_bundled_approach_commands() -> list[str]:
    return _scan_markdown_command_lines(
        PLAN_SESSION_APPROACH_PATH
    ) + _scan_markdown_command_lines(RESEARCH_SESSION_APPROACH_PATH)


def _scan_contributor_approach_commands() -> list[str]:
    violations: list[str] = []
    for path in CONTRIBUTOR_APPROACH_DOC_PATHS:
        violations.extend(_scan_markdown_command_lines(path))
    return violations


def _scan_prompt_definition_commands() -> list[str]:
    return _scan_markdown_command_lines(LOOP_IMPLEMENTATION_PROMPT_PATH)


def _scan_check_commands() -> list[str]:
    if not CHECKS_PATH.is_file():
        return []

    document = yaml.safe_load(CHECKS_PATH.read_text(encoding="utf-8")) or {}
    checks = document.get("checks") if isinstance(document, dict) else None
    if not isinstance(checks, dict):
        return []

    violations: list[str] = []
    for check_id in sorted(checks):
        check = checks[check_id]
        if not isinstance(check, dict):
            continue
        if check.get("type") != "command":
            continue

        command = check.get("command")
        violation_reason = _command_policy_violation(command)
        if violation_reason is None:
            continue
        violations.append(
            (
                f"{CHECKS_PATH.as_posix()}:checks.{check_id}.command {violation_reason} "
                f"`{_format_command(command)}`; {REMEDIATION}"
            )
        )

    return violations


def main() -> int:
    """Check scoped loop commands for forbidden in-repo uvx self-invocation."""
    violations = sorted(
        set(
            _scan_feature_verification_commands(Path("."))
            + _scan_smoke_template_commands()
            + _scan_bundled_approach_commands()
            + _scan_contributor_approach_commands()
            + _scan_prompt_definition_commands()
            + _scan_check_commands()
        )
    )
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "All scoped loop commands use source-first workspace execution forms."
        if status == RuleStatus.PASS
        else (
            "Detected forbidden in-repo uvx self-invocation patterns in loop command "
            "surfaces."
        )
    )

    emit_fitness_result(
        FitnessRuleResult(
            contract_version=CONTRACT_VERSION,
            rule_id=RULE_ID,
            status=status,
            severity=RuleSeverity.ERROR,
            summary=summary,
            violations=violations,
        )
    )
    return 0 if status == RuleStatus.PASS else 1


if __name__ == "__main__":
    raise SystemExit(main())
