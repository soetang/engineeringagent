from __future__ import annotations

import argparse
import ast
from pathlib import Path
from typing import NamedTuple

import yaml

from engineeringagent.checks import emit_fitness_result
from engineeringagent.checks.fitness.local_support_loader import load_local_support_module
from engineeringagent.checks.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


_support = load_local_support_module(
    "hermetic_fitness_test_isolation_support",
    caller_file=Path(__file__),
)
TaintState = _support.TaintState
is_tainted = _support.is_tainted
mapping_taint_keys = _support.mapping_taint_keys
scan_statement = _support.scan_statement
tainted_source_names = _support.tainted_source_names


RULE_ID = "architecture.hermetic-fitness-test-isolation"
_TESTS_ROOT = Path("tests/fitness")
_DEFAULT_POLICY = (
    Path(__file__).resolve().parent
    / "policies"
    / "hermetic_fitness_test_isolation.yaml"
)


class ForwardedSink(NamedTuple):
    """Maps a helper parameter to a checker scan-target sink."""

    pattern: str
    parameter_name: str | None = None
    parameter_index: int | None = None
    var_keyword_name: str | None = None


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", default=str(_DEFAULT_POLICY))
    return parser.parse_args()


def _resolve_config_file(config_file: str) -> Path:
    path = Path(config_file)
    if not path.is_file():
        raise ValueError(f"policy config not found: {path}")
    return path


def _load_policy(config_file: Path) -> set[str]:
    try:
        payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"failed to read policy config: {config_file}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"policy config is not valid YAML: {config_file}") from exc

    if not isinstance(payload, dict):
        raise ValueError("policy config must be a mapping")

    modules = payload.get("integration_test_modules", [])
    if not isinstance(modules, list) or not all(
        isinstance(item, str) and item.strip() for item in modules
    ):
        raise ValueError(
            "policy field 'integration_test_modules' must be a list of non-empty strings"
        )

    return {
        item.replace("\\", "/").strip().lstrip("./")
        for item in modules
        if item.strip()
    }


def _iter_fitness_test_files(project_root: Path) -> list[Path]:
    tests_root = project_root / _TESTS_ROOT
    if not tests_root.exists():
        return []
    return sorted(path for path in tests_root.rglob("*.py") if path.is_file())


def _call_name(call: ast.Call) -> str | None:
    if isinstance(call.func, ast.Name):
        return call.func.id
    if isinstance(call.func, ast.Attribute):
        if isinstance(call.func.value, ast.Name):
            return f"{call.func.value.id}.{call.func.attr}"
        return call.func.attr
    return None


def _forwarding_contract_lookup_keys(call: ast.Call) -> tuple[str, ...]:
    call_name = _call_name(call)
    if call_name is None:
        return ()

    if (
        isinstance(call.func, ast.Attribute)
        and isinstance(call.func.value, ast.Name)
        and call.func.value.id in {"self", "cls"}
    ):
        return (call_name, call.func.attr)

    return (call_name,)


def _collect_subprocess_imports(tree: ast.Module) -> tuple[set[str], set[str]]:
    subprocess_modules: set[str] = set()
    direct_subprocess_calls: set[str] = set()

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "subprocess":
                    subprocess_modules.add(alias.asname or alias.name)
            continue

        if not isinstance(node, ast.ImportFrom):
            continue
        if node.level != 0 or node.module != "subprocess":
            continue

        for alias in node.names:
            if alias.name == "*":
                direct_subprocess_calls.update(
                    {"run", "Popen", "call", "check_call", "check_output"}
                )
                continue
            direct_subprocess_calls.add(alias.asname or alias.name)

    return subprocess_modules, direct_subprocess_calls


def _is_subprocess_call(
    call: ast.Call,
    *,
    subprocess_modules: set[str],
    direct_subprocess_calls: set[str],
) -> bool:
    if isinstance(call.func, ast.Attribute) and isinstance(call.func.value, ast.Name):
        return call.func.value.id in subprocess_modules
    if isinstance(call.func, ast.Name):
        return call.func.id in direct_subprocess_calls
    return False


def _parameter_index_map(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
) -> dict[str, int]:
    parameter_names = [arg.arg for arg in node.args.posonlyargs]
    parameter_names.extend(arg.arg for arg in node.args.args)
    if parameter_names and parameter_names[0] in {"self", "cls"}:
        parameter_names = parameter_names[1:]
    return {name: index for index, name in enumerate(parameter_names)}


def _sink_pattern(
    call: ast.Call,
    *,
    tainted_names: set[str],
    subprocess_modules: set[str],
    direct_subprocess_calls: set[str],
) -> str | None:
    call_name = _call_name(call)

    if call_name == "_run_checker":
        if call.args and is_tainted(call.args[0], tainted_names=tainted_names):
            return "_run_checker project_root"
        for keyword in call.keywords:
            if keyword.arg in {"project_root", "cwd"} and keyword.value is not None:
                if is_tainted(keyword.value, tainted_names=tainted_names):
                    return f"_run_checker {keyword.arg}"

    if call_name == "execute_rule_definition":
        for keyword in call.keywords:
            if keyword.arg == "project_root" and keyword.value is not None:
                if is_tainted(keyword.value, tainted_names=tainted_names):
                    return "execute_rule_definition project_root"

    if _is_subprocess_call(
        call,
        subprocess_modules=subprocess_modules,
        direct_subprocess_calls=direct_subprocess_calls,
    ):
        for keyword in call.keywords:
            if keyword.arg == "cwd" and keyword.value is not None:
                if is_tainted(keyword.value, tainted_names=tainted_names):
                    return "subprocess cwd"

    return None


def _forwarded_parameters(
    expr: ast.AST,
    *,
    pattern: str,
    parameter_indexes: dict[str, int],
    tainted_sources: dict[str, set[str]],
) -> list[ForwardedSink]:
    forwarded: list[ForwardedSink] = []
    for parameter_name in sorted(
        tainted_source_names(expr, tainted_sources=tainted_sources)
    ):
        parameter_index = parameter_indexes.get(parameter_name)
        if parameter_index is None:
            continue
        forwarded.append(
            ForwardedSink(
                pattern=pattern,
                parameter_name=parameter_name,
                parameter_index=parameter_index,
            )
        )
    return forwarded


def _collect_forwarding_contract(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    subprocess_modules: set[str],
    direct_subprocess_calls: set[str],
) -> list[ForwardedSink]:
    parameter_indexes = _parameter_index_map(node)
    var_keyword_name = node.args.kwarg.arg if node.args.kwarg is not None else None
    forwarded: list[ForwardedSink] = []
    tainted_sources: dict[str, set[str]] = {
        parameter_name: {parameter_name} for parameter_name in parameter_indexes
    }

    def _track_assignment(name: str, value: ast.AST) -> None:
        tainted_source_names_found = tainted_source_names(
            value,
            tainted_sources=tainted_sources,
        )
        if tainted_source_names_found:
            tainted_sources[name] = tainted_source_names_found
            return
        tainted_sources.pop(name, None)

    def _scan_expression(expr: ast.AST) -> None:
        for child in ast.walk(expr):
            if not isinstance(child, ast.Call):
                continue

            call_name = _call_name(child)
            if call_name == "_run_checker":
                if child.args:
                    forwarded.extend(
                        _forwarded_parameters(
                            child.args[0],
                            pattern="_run_checker project_root",
                            parameter_indexes=parameter_indexes,
                            tainted_sources=tainted_sources,
                        )
                    )
                for keyword in child.keywords:
                    if keyword.arg in {"project_root", "cwd"} and keyword.value is not None:
                        forwarded.extend(
                            _forwarded_parameters(
                                keyword.value,
                                pattern=f"_run_checker {keyword.arg}",
                                parameter_indexes=parameter_indexes,
                                tainted_sources=tainted_sources,
                            )
                        )

            if call_name == "execute_rule_definition":
                for keyword in child.keywords:
                    if keyword.arg == "project_root" and keyword.value is not None:
                        forwarded.extend(
                            _forwarded_parameters(
                                keyword.value,
                                pattern="execute_rule_definition project_root",
                                parameter_indexes=parameter_indexes,
                                tainted_sources=tainted_sources,
                            )
                        )
                    if (
                        keyword.arg is None
                        and var_keyword_name is not None
                        and isinstance(keyword.value, ast.Name)
                        and keyword.value.id == var_keyword_name
                    ):
                        forwarded.append(
                            ForwardedSink(
                                pattern="execute_rule_definition project_root",
                                var_keyword_name=var_keyword_name,
                            )
                        )

            if _is_subprocess_call(
                child,
                subprocess_modules=subprocess_modules,
                direct_subprocess_calls=direct_subprocess_calls,
            ):
                for keyword in child.keywords:
                    if keyword.arg == "cwd" and keyword.value is not None:
                        forwarded.extend(
                            _forwarded_parameters(
                                keyword.value,
                                pattern="subprocess cwd",
                                parameter_indexes=parameter_indexes,
                                tainted_sources=tainted_sources,
                            )
                        )

    def _scan_statement(statement: ast.stmt) -> None:
        if isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            return
        scan_statement(
            statement,
            scan_expression=_scan_expression,
            scan_statement_recursively=_scan_statement,
            handle_name_assignment=_track_assignment,
            skip_classdefs=False,
        )

    for statement in node.body:
        _scan_statement(statement)

    return forwarded


def _collect_nested_forwarding_contracts(
    statements: list[ast.stmt],
    *,
    subprocess_modules: set[str],
    direct_subprocess_calls: set[str],
) -> dict[str, list[ForwardedSink]]:
    contracts: dict[str, list[ForwardedSink]] = {}

    for statement in statements:
        if isinstance(statement, ast.ClassDef):
            contracts.update(
                _collect_nested_forwarding_contracts(
                    statement.body,
                    subprocess_modules=subprocess_modules,
                    direct_subprocess_calls=direct_subprocess_calls,
                )
            )
            continue
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        forwarded = _collect_forwarding_contract(
            statement,
            subprocess_modules=subprocess_modules,
            direct_subprocess_calls=direct_subprocess_calls,
        )
        if forwarded:
            contracts[statement.name] = forwarded
            contracts[f"self.{statement.name}"] = forwarded
            contracts[f"cls.{statement.name}"] = forwarded

        contracts.update(
            _collect_nested_forwarding_contracts(
                statement.body,
                subprocess_modules=subprocess_modules,
                direct_subprocess_calls=direct_subprocess_calls,
            )
        )

    return contracts


def _collect_forwarding_contracts(
    tree: ast.Module,
) -> dict[str, list[ForwardedSink]]:
    subprocess_modules, direct_subprocess_calls = _collect_subprocess_imports(tree)
    contracts: dict[str, list[ForwardedSink]] = {}

    for statement in tree.body:
        if isinstance(statement, ast.ClassDef):
            contracts.update(
                _collect_nested_forwarding_contracts(
                    statement.body,
                    subprocess_modules=subprocess_modules,
                    direct_subprocess_calls=direct_subprocess_calls,
                )
            )
            continue
        if not isinstance(statement, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue

        forwarded = _collect_forwarding_contract(
            statement,
            subprocess_modules=subprocess_modules,
            direct_subprocess_calls=direct_subprocess_calls,
        )
        if forwarded:
            contracts[statement.name] = forwarded

    return contracts


def _collect_function_violations(
    node: ast.FunctionDef | ast.AsyncFunctionDef,
    *,
    file_rel: Path,
    forwarding_contracts: dict[str, list[ForwardedSink]],
    subprocess_modules: set[str],
    direct_subprocess_calls: set[str],
    violations: list[str],
) -> None:
    scoped_forwarding_contracts = dict(forwarding_contracts)
    scoped_forwarding_contracts.update(
        _collect_nested_forwarding_contracts(
            node.body,
            subprocess_modules=subprocess_modules,
            direct_subprocess_calls=direct_subprocess_calls,
        )
    )
    taint_state = TaintState()

    def _scan_expression(expr: ast.AST) -> None:
        for child in ast.walk(expr):
            if not isinstance(child, ast.Call):
                continue
            pattern = _sink_pattern(
                child,
                tainted_names=taint_state.tainted_names,
                subprocess_modules=subprocess_modules,
                direct_subprocess_calls=direct_subprocess_calls,
            )
            if pattern is not None:
                violations.append(
                    f"{file_rel}:{child.lineno} fitness tests must not use "
                    f"repo_root as checker scan target ({pattern})"
                )

            forwarded_sinks: list[ForwardedSink] = []
            for key in _forwarding_contract_lookup_keys(child):
                forwarded_sinks.extend(scoped_forwarding_contracts.get(key, []))
            if not forwarded_sinks:
                continue
            for forwarded_sink in forwarded_sinks:
                if (
                    forwarded_sink.parameter_index is not None
                    and forwarded_sink.parameter_index < len(child.args)
                    and is_tainted(
                        child.args[forwarded_sink.parameter_index],
                        tainted_names=taint_state.tainted_names,
                    )
                ):
                    violations.append(
                        f"{file_rel}:{child.lineno} fitness tests must not use "
                        f"repo_root as checker scan target ({forwarded_sink.pattern})"
                    )
                    continue

                if forwarded_sink.parameter_name is not None:
                    for keyword in child.keywords:
                        if (
                            keyword.arg == forwarded_sink.parameter_name
                            and keyword.value is not None
                            and is_tainted(
                                keyword.value,
                                tainted_names=taint_state.tainted_names,
                            )
                        ):
                            violations.append(
                                f"{file_rel}:{child.lineno} fitness tests must not use "
                                f"repo_root as checker scan target ({forwarded_sink.pattern})"
                            )
                            break

                if forwarded_sink.var_keyword_name is not None:
                    for keyword in child.keywords:
                        if keyword.arg is not None:
                            continue
                        tainted_keys = mapping_taint_keys(
                            keyword.value,
                            tainted_names=taint_state.tainted_names,
                            tainted_mapping_keys=taint_state.tainted_mapping_keys,
                        )
                        if "project_root" in tainted_keys:
                            violations.append(
                                f"{file_rel}:{child.lineno} fitness tests must not use "
                                f"repo_root as checker scan target ({forwarded_sink.pattern})"
                            )
                            break

    def _scan_statement(statement: ast.stmt) -> None:
        scan_statement(
            statement,
            scan_expression=_scan_expression,
            scan_statement_recursively=_scan_statement,
            handle_name_assignment=taint_state.update_assignment,
            skip_classdefs=True,
        )

    for statement in node.body:
        _scan_statement(statement)


def _collect_violations(project_root: Path, *, config_file: Path) -> list[str]:
    allowlisted_modules = _load_policy(config_file)
    violations: list[str] = []

    for path in _iter_fitness_test_files(project_root):
        file_rel = path.relative_to(project_root)
        if file_rel.as_posix() in allowlisted_modules:
            continue

        try:
            tree = ast.parse(path.read_text(encoding="utf-8"))
        except OSError as exc:
            violations.append(f"{file_rel}:1 failed to read for hermetic scan: {exc}")
            continue
        except SyntaxError as exc:
            violations.append(
                f"{file_rel}:{exc.lineno or 1} failed to parse for hermetic scan"
            )
            continue

        forwarding_contracts = _collect_forwarding_contracts(tree)
        subprocess_modules, direct_subprocess_calls = _collect_subprocess_imports(tree)
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                _collect_function_violations(
                    node,
                    file_rel=file_rel,
                    forwarding_contracts=forwarding_contracts,
                    subprocess_modules=subprocess_modules,
                    direct_subprocess_calls=direct_subprocess_calls,
                    violations=violations,
                )
                continue
            if isinstance(node, ast.ClassDef):
                for class_statement in node.body:
                    if not isinstance(
                        class_statement, (ast.FunctionDef, ast.AsyncFunctionDef)
                    ):
                        continue
                    _collect_function_violations(
                        class_statement,
                        file_rel=file_rel,
                        forwarding_contracts=forwarding_contracts,
                        subprocess_modules=subprocess_modules,
                        direct_subprocess_calls=direct_subprocess_calls,
                        violations=violations,
                    )

    return sorted(set(violations))


def main() -> int:
    """Run the hermetic fitness test isolation rule."""
    try:
        config_file = _resolve_config_file(_parse_args().config_file)
        violations = _collect_violations(Path("."), config_file=config_file)
        status = RuleStatus.PASS if not violations else RuleStatus.FAIL
        summary = (
            "Fitness tests keep checker scan targets hermetic."
            if status == RuleStatus.PASS
            else f"Detected {len(violations)} hermetic fitness test violation(s)."
        )
    except ValueError as exc:
        status = RuleStatus.ERROR
        summary = f"Hermetic fitness test scan failed: {exc}"
        violations = [summary]
    except OSError as exc:
        status = RuleStatus.ERROR
        summary = f"Hermetic fitness test scan failed: {exc}"
        violations = [summary]

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
