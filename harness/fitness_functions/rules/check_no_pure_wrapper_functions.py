from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import Any

import yaml

from engineeringagent.adapters.quality.fitness import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.no-pure-wrapper-functions"
_REMEDIATION_ORDER = (
    "remediation order: (1) move logic to canonical domain; "
    "(2) promote/rename canonical function; "
    "(3) replace wrapper with explicit local logic; "
    "(4) only then add allowlist exception with rationale."
)
_DEFAULT_POLICY_PATH = (
    Path(__file__).resolve().parent.parent
    / "policies"
    / "no_pure_wrapper_functions.yaml"
)


class _RuntimePolicyError(ValueError):
    pass


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", dest="config_file", default=None)
    return parser.parse_args()


def _load_policy(config_file: str | None) -> dict[str, Any]:
    policy_path = Path(config_file) if config_file is not None else _DEFAULT_POLICY_PATH
    try:
        payload = yaml.safe_load(policy_path.read_text(encoding="utf-8"))
    except OSError as exc:
        raise _RuntimePolicyError(
            f"unable to read config file {policy_path}: {exc}"
        ) from exc
    except yaml.YAMLError as exc:
        raise _RuntimePolicyError(
            f"unable to parse config file {policy_path}: {exc}"
        ) from exc

    if not isinstance(payload, dict):
        raise _RuntimePolicyError("config file must contain a YAML mapping")
    return payload


def _config_string(policy: dict[str, Any], key: str) -> str:
    value = policy.get(key)
    if not isinstance(value, str) or not value.strip():
        raise _RuntimePolicyError(f"config key '{key}' must be a non-empty string")
    return value.strip()


def _config_root_paths(policy: dict[str, Any], key: str) -> tuple[Path, ...]:
    value = policy.get(key)
    error = f"config key '{key}' must be a non-empty list of relative paths"
    if not isinstance(value, list) or not value:
        raise _RuntimePolicyError(error)

    roots: list[Path] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise _RuntimePolicyError(error)
        path = Path(item.strip())
        if path.is_absolute() or ".." in path.parts:
            raise _RuntimePolicyError(error)
        roots.append(path)

    if len(set(roots)) != len(roots):
        raise _RuntimePolicyError(f"config key '{key}' must not contain duplicates")
    return tuple(roots)


def _config_allowlist(
    policy: dict[str, Any], key: str
) -> tuple[tuple[str, str, str, str], ...]:
    value = policy.get(key)
    if value is None:
        return ()
    if not isinstance(value, list):
        raise _RuntimePolicyError(f"config key '{key}' must be a list")

    parsed_entries: list[tuple[str, str, str, str]] = []
    for index, entry in enumerate(value):
        if not isinstance(entry, dict):
            raise _RuntimePolicyError(
                f"config key '{key}[{index}]' must be a mapping"
            )
        rel_path = entry.get("path")
        function_name = entry.get("function")
        rationale = entry.get("rationale")
        remediation = entry.get("remediation")
        if not isinstance(rel_path, str) or not rel_path.strip():
            raise _RuntimePolicyError(
                f"config key '{key}[{index}].path' must be a non-empty string"
            )
        if not isinstance(function_name, str) or not function_name.strip():
            raise _RuntimePolicyError(
                f"config key '{key}[{index}].function' must be a non-empty string"
            )
        if not isinstance(rationale, str) or not rationale.strip():
            raise _RuntimePolicyError(
                f"config key '{key}[{index}].rationale' must be a non-empty string"
            )
        if not isinstance(remediation, str) or not remediation.strip():
            raise _RuntimePolicyError(
                f"config key '{key}[{index}].remediation' must be a non-empty string"
            )
        normalized_path = rel_path.strip()
        path_obj = Path(normalized_path)
        if path_obj.is_absolute() or ".." in path_obj.parts:
            raise _RuntimePolicyError(
                f"config key '{key}[{index}].path' must be a relative path"
            )
        normalized_function = function_name.strip()
        parsed_entries.append(
            (
                path_obj.as_posix(),
                normalized_function,
                rationale.strip(),
                remediation.strip(),
            )
        )

    if len(set((path, function) for path, function, _, _ in parsed_entries)) != len(
        parsed_entries
    ):
        raise _RuntimePolicyError(
            f"config key '{key}' must not contain duplicate path/function entries"
        )
    return tuple(parsed_entries)


def _iter_python_files(project_root: Path, roots: tuple[Path, ...]) -> list[Path]:
    paths: list[Path] = []
    for root in roots:
        root_path = project_root / root
        if not root_path.exists():
            continue
        paths.extend(path for path in root_path.rglob("*.py") if path.is_file())
    return sorted(paths, key=lambda path: path.relative_to(project_root).as_posix())


def _single_statement_body(node: ast.FunctionDef | ast.AsyncFunctionDef) -> list[ast.stmt]:
    statements = list(node.body)
    if statements and isinstance(statements[0], ast.Expr) and isinstance(
        statements[0].value, ast.Constant
    ):
        if isinstance(statements[0].value.value, str):
            statements = statements[1:]
    return statements


def _return_call_target(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> ast.Call | None:
    statements = _single_statement_body(node)
    if len(statements) != 1:
        return None
    statement = statements[0]
    if not isinstance(statement, ast.Return):
        return None

    value = statement.value
    if isinstance(value, ast.Call):
        return value
    if isinstance(node, ast.AsyncFunctionDef) and isinstance(value, ast.Await):
        if isinstance(value.value, ast.Call):
            return value.value
    return None


def _parameter_sequence(
    args: ast.arguments,
) -> tuple[tuple[str, ...], str | None, tuple[str, ...], str | None]:
    positional = tuple(
        arg.arg for arg in (*args.posonlyargs, *args.args)
    )
    vararg = args.vararg.arg if args.vararg is not None else None
    kwonly = tuple(arg.arg for arg in args.kwonlyargs)
    kwarg = args.kwarg.arg if args.kwarg is not None else None
    return positional, vararg, kwonly, kwarg


def _is_passthrough_call(call: ast.Call, args: ast.arguments) -> bool:
    positional, vararg, kwonly, kwarg = _parameter_sequence(args)

    expected_positional_index = 0
    forwarded_positional: set[str] = set()
    saw_vararg_unpack = False
    for arg in call.args:
        if isinstance(arg, ast.Starred):
            if (
                vararg is None
                or saw_vararg_unpack
                or not isinstance(arg.value, ast.Name)
                or arg.value.id != vararg
            ):
                return False
            saw_vararg_unpack = True
            continue

        if expected_positional_index >= len(positional):
            return False
        if not isinstance(arg, ast.Name):
            return False
        expected_name = positional[expected_positional_index]
        if arg.id != expected_name:
            return False
        forwarded_positional.add(expected_name)
        expected_positional_index += 1

    if vararg is not None and not saw_vararg_unpack:
        return False

    seen_kwonly: set[str] = set()
    saw_kwarg_unpack = False
    for keyword in call.keywords:
        if keyword.arg is None:
            if (
                kwarg is None
                or saw_kwarg_unpack
                or not isinstance(keyword.value, ast.Name)
                or keyword.value.id != kwarg
            ):
                return False
            saw_kwarg_unpack = True
            continue

        if keyword.arg in kwonly:
            if keyword.arg in seen_kwonly:
                return False
            if not isinstance(keyword.value, ast.Name):
                return False
            if keyword.value.id != keyword.arg:
                return False
            seen_kwonly.add(keyword.arg)
            continue
        if keyword.arg in positional:
            if keyword.arg in forwarded_positional:
                return False
            if not isinstance(keyword.value, ast.Name):
                return False
            if keyword.value.id != keyword.arg:
                return False
            forwarded_positional.add(keyword.arg)
            continue
        return False

    if len(forwarded_positional) != len(positional):
        return False
    if set(kwonly) != seen_kwonly:
        return False
    if kwarg is not None and not saw_kwarg_unpack:
        return False
    return True


def _collect_wrapper_functions(
    tree: ast.AST,
) -> list[tuple[str, int]]:
    wrappers: list[tuple[str, int]] = []

    class _Visitor(ast.NodeVisitor):
        """Collect wrapper-shaped function definitions with qualified names."""

        def __init__(self) -> None:
            """Initialize class/function nesting state."""
            self._stack: list[str] = []

        # AST node visitor names are part of the stdlib interface.
        # pylint: disable=invalid-name
        def visit_ClassDef(self, node: ast.ClassDef) -> None:
            """Track class nesting while traversing descendants."""
            self._stack.append(node.name)
            self.generic_visit(node)
            self._stack.pop()

        def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
            """Inspect sync function nodes for pure wrapper behavior."""
            self._collect(node)

        def visit_AsyncFunctionDef(self, node: ast.AsyncFunctionDef) -> None:
            """Inspect async function nodes for pure wrapper behavior."""
            self._collect(node)

        def _collect(self, node: ast.FunctionDef | ast.AsyncFunctionDef) -> None:
            self._stack.append(node.name)
            call = _return_call_target(node)
            if call is not None and _is_passthrough_call(call, node.args):
                wrappers.append((".".join(self._stack), node.lineno))
            self.generic_visit(node)
            self._stack.pop()

    _Visitor().visit(tree)
    return wrappers


def _resolve_scan_roots(project_root: Path, roots: tuple[Path, ...]) -> list[str]:
    violations: list[str] = []
    for root in roots:
        root_path = project_root / root
        if not root_path.is_dir():
            violations.append(f"{root}:1 missing configured scan root")
    return violations


def _collect_violations(
    project_root: Path,
    roots: tuple[Path, ...],
    *,
    allowlist: tuple[tuple[str, str, str, str], ...],
) -> list[str]:
    violations = _resolve_scan_roots(project_root, roots)
    if violations:
        return sorted(violations)

    allowlist_index = {(path, function) for path, function, _, _ in allowlist}

    for file_path in _iter_python_files(project_root, roots):
        relative = file_path.relative_to(project_root).as_posix()
        try:
            source = file_path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=relative)
        except (OSError, SyntaxError, UnicodeError) as exc:
            line = exc.lineno if isinstance(exc, SyntaxError) and exc.lineno else 1
            violations.append(
                f"{relative}:{line} failed to parse for pure-wrapper scan: {exc}"
            )
            continue

        for function_name, line in _collect_wrapper_functions(tree):
            if (relative, function_name) in allowlist_index:
                continue
            violations.append(
                f"{relative}:{line} pure wrapper function '{function_name}' forwards all parameters directly; {_REMEDIATION_ORDER}"
            )
    return sorted(violations)


def main() -> int:
    """Run the no-pure-wrapper-functions fitness rule policy contract."""
    args = _parse_args()

    try:
        policy = _load_policy(args.config_file)
        policy_rule_id = _config_string(policy, "rule_id")
        if policy_rule_id != RULE_ID:
            raise _RuntimePolicyError(
                f"rule_id must match {RULE_ID}: {policy_rule_id!r}"
            )
        scan_roots = _config_root_paths(policy, "scan_roots")
        allowlist = _config_allowlist(policy, "allowlist")
        violations = _collect_violations(Path("."), scan_roots, allowlist=allowlist)
        status = RuleStatus.PASS if not violations else RuleStatus.FAIL
        summary = (
            "No pure wrapper function violations detected."
            if status == RuleStatus.PASS
            else f"Detected {len(violations)} pure wrapper function violation(s)."
        )
    except _RuntimePolicyError as exc:
        status = RuleStatus.FAIL
        summary = "No-pure-wrapper policy configuration is invalid."
        violations = [str(exc)]

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
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
