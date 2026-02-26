from __future__ import annotations

import ast
from pathlib import Path

from engineeringagent.checks import emit_result_envelope
from engineeringagent.checks.fitness.boundary_reporting import (
    build_boundary_rule_result,
)
from engineeringagent.checks.fitness.scope_traversal import (
    PROMPT_RENDERER_MODULE,
    collect_call_symbol_violations,
    collect_function_symbol_call_violations,
    collect_import_from_symbol_violations,
    collect_loop_boundary_rule_violations,
)


RULE_ID = "architecture.checks-own-prompt-feedback-rendering"

_BANNED_CHECKS_BUILDER_CALLS = {
    "build_command_failure_feedback",
    "build_fitness_failure_feedback",
    "build_reviewer_feedback",
}
_BANNED_PROMPT_SYMBOLS = {
    "build_fitness_failure_feedback",
    "build_reviewer_feedback",
}

_REMEDIATION = (
    "move checks-specific feedback shaping into checks strategies and forward "
    "run_checks(...).prompt_feedback as-is from loop/prompt wiring"
)


def _prompt_symbol_violations(relative: Path, tree: ast.AST) -> list[str]:
    violations = collect_import_from_symbol_violations(
        tree,
        forbidden_symbols=_BANNED_PROMPT_SYMBOLS,
        message_builder=lambda lineno, symbol: (
            f"{relative}:{lineno} imports '{symbol}' in prompt renderer; {_REMEDIATION}"
        ),
    )
    violations.extend(
        collect_call_symbol_violations(
            tree,
            forbidden_symbols=_BANNED_PROMPT_SYMBOLS,
            message_builder=lambda lineno, symbol: (
                f"{relative}:{lineno} calls '{symbol}' in prompt renderer; "
                f"{_REMEDIATION}"
            ),
        )
    )
    return sorted(violations)


def _loop_checks_feedback_violations(relative: Path, tree: ast.AST) -> list[str]:
    return collect_function_symbol_call_violations(
        tree,
        trigger_symbols={"run_checks"},
        forbidden_symbols=_BANNED_CHECKS_BUILDER_CALLS,
        message_builder=lambda lineno, symbol: (
            f"{relative}:{lineno} calls checks-specific feedback builder "
            f"'{symbol}' inside run_checks flow; {_REMEDIATION}"
        ),
    )


def _checks_owned_prompt_feedback_violations(project_root: Path) -> list[str]:
    return collect_loop_boundary_rule_violations(
        project_root,
        include_prompt_renderer=True,
        remediation=_REMEDIATION,
        module_violations=_module_prompt_feedback_violations,
    )


def _module_prompt_feedback_violations(relative: Path, tree: ast.AST) -> list[str]:
    if relative == PROMPT_RENDERER_MODULE:
        return _prompt_symbol_violations(relative, tree)
    return _loop_checks_feedback_violations(relative, tree)


def main() -> int:
    """Run checks-owned prompt-feedback rendering boundary rule."""
    violations = _checks_owned_prompt_feedback_violations(Path("."))
    emit_result_envelope(
        build_boundary_rule_result(
            rule_id=RULE_ID,
            violations=violations,
            pass_summary="Checks-owned prompt-feedback rendering boundary satisfied.",
            fail_summary_label="checks prompt-feedback boundary",
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
