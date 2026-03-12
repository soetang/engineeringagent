from __future__ import annotations

import argparse
from pathlib import Path

import yaml

from engineeringagent.checks import emit_fitness_result
from engineeringagent.adapters.quality.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)


RULE_ID = "architecture.test-layout-module-mirroring"
_SOURCE_PACKAGE_ROOT = Path("src/engineeringagent")
_TESTS_ROOT = Path("tests")
_DEFAULT_POLICY = (
    Path(__file__).resolve().parent.parent
    / "policies"
    / "test_layout_module_mirroring.yaml"
)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config-file", default=str(_DEFAULT_POLICY))
    return parser.parse_args()


def _resolve_config_file(config_file: str) -> Path:
    path = Path(config_file)
    if not path.is_file():
        raise ValueError(f"policy config not found: {path}")
    return path


def _require_string_list(payload: dict[str, object], field: str) -> list[str]:
    value = payload.get(field)
    if not isinstance(value, list) or not all(
        isinstance(item, str) and item for item in value
    ):
        raise ValueError(f"policy field '{field}' must be a list of non-empty strings")
    return value


def _normalize_exception_list(values: list[str], *, strip_tests_prefix: bool) -> set[str]:
    normalized = set()
    for value in values:
        candidate = value.replace("\\", "/").strip().strip("/")
        if strip_tests_prefix and candidate.startswith("tests/"):
            candidate = candidate.removeprefix("tests/")
        if not candidate:
            raise ValueError("exception path cannot be empty")
        normalized.add(candidate)
    return normalized


def _load_policy(config_file: Path) -> tuple[set[str], set[str], set[str], set[str]]:
    try:
        payload = yaml.safe_load(config_file.read_text(encoding="utf-8"))
    except OSError as exc:
        raise ValueError(f"failed to read policy config: {config_file}") from exc
    except yaml.YAMLError as exc:
        raise ValueError(f"policy config is not valid YAML: {config_file}") from exc

    if not isinstance(payload, dict):
        raise ValueError("policy config must be a mapping")

    exception_dirs = _normalize_exception_list(
        _require_string_list(payload, "exception_root_dirs"),
        strip_tests_prefix=True,
    )
    exception_files = _normalize_exception_list(
        _require_string_list(payload, "exception_root_files"),
        strip_tests_prefix=True,
    )
    alias_roots = set(
        item.strip().replace("\\", "/").strip("/")
        for item in _require_string_list(payload, "alias_topic_roots")
        if item.strip()
    )
    forbidden_tests = _normalize_exception_list(
        _require_string_list(payload, "forbidden_test_paths"),
        strip_tests_prefix=False,
    )
    if not alias_roots:
        raise ValueError("alias_topic_roots must contain at least one entry")

    return exception_dirs, exception_files, alias_roots, forbidden_tests


def _iter_python_test_files(project_root: Path) -> list[Path]:
    tests_root = project_root / _TESTS_ROOT
    if not tests_root.exists():
        return []
    return sorted(path for path in tests_root.rglob("*.py") if path.is_file())


def _test_layout_violations(project_root: Path) -> list[str]:
    config = _load_policy(_resolve_config_file(_parse_args().config_file))
    exception_dirs, exception_files, alias_roots, forbidden_tests = config

    tests_root = project_root / _TESTS_ROOT
    source_root = project_root / _SOURCE_PACKAGE_ROOT
    if not source_root.exists():
        return [f"missing source package root: {_SOURCE_PACKAGE_ROOT}"]
    if not tests_root.exists():
        return []

    violations: list[str] = []
    for path in _iter_python_test_files(project_root):
        rel_path = path.relative_to(project_root).as_posix()
        rel_test = path.relative_to(tests_root).as_posix()
        rel_parts = rel_test.split("/")

        if rel_path in forbidden_tests:
            violations.append(
                f"{rel_path}: legacy test path is forbidden; move it under the "
                "mirrored source module path."
            )
            continue

        if len(rel_parts) == 1:
            if rel_test not in exception_files:
                violations.append(
                    f"{rel_path}: banned root-level test module; move into a module "
                    "folder or explicit exception."
                )
            continue

        topic = rel_parts[0]
        if topic in alias_roots:
            violations.append(
                f"{rel_path}: disallowed alias topic root '{topic}/'; use module-mirrored path."
            )
            continue

        if topic in exception_dirs:
            continue

        source_target = source_root / Path(*rel_parts[:-1])
        source_target_py = source_target.with_suffix(".py")
        if source_target.is_file() and source_target.suffix == ".py":
            continue
        if source_target_py.exists() and source_target_py.is_file():
            continue
        if source_target.is_dir() and (source_target / "__init__.py").is_file():
            continue
        violations.append(
            f"{rel_path}: not mirrored by src module path "
            f"{_SOURCE_PACKAGE_ROOT / Path(*rel_parts[:-1])}"
        )

    return sorted(set(violations))


def main() -> int:
    """Run the test layout module-mirroring fitness rule."""
    try:
        violations = _test_layout_violations(Path("."))
        status = RuleStatus.PASS if not violations else RuleStatus.FAIL
        summary = (
            "Test layout module-mirroring policy is satisfied."
            if status == RuleStatus.PASS
            else f"Detected {len(violations)} test layout policy violation(s)."
        )
    except ValueError as exc:
        status = RuleStatus.ERROR
        summary = f"Test layout policy scan failed: {exc}"
        violations = [summary]
    except OSError as exc:
        status = RuleStatus.ERROR
        summary = f"Test layout policy scan failed: {exc}"
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
