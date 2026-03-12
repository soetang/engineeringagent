from __future__ import annotations

import ast
from pathlib import Path
import textwrap

import pytest
from engineeringagent.presentation import cli as cli_module
from engineeringagent.checks import HarnessCheckPhase
from engineeringagent.adapters.runtime import iteration_phases as loop_phases


def _forbidden_imports_from_import(node: ast.Import) -> set[str]:
    return {
        "import engineeringagent.specs"
        for alias in node.names
        if alias.name == "engineeringagent.specs"
    }


def _forbidden_imports_from_absolute_from(node: ast.ImportFrom) -> set[str]:
    if node.module == "engineeringagent":
        return {
            "from engineeringagent import specs"
            for alias in node.names
            if alias.name == "specs"
        }
    if node.module == "engineeringagent.specs":
        return {"from engineeringagent.specs import ..."}
    return set()


def _forbidden_imports_from_relative_from(node: ast.ImportFrom) -> set[str]:
    if node.module is None:
        return {
            f"from {'.' * node.level} import specs"
            for alias in node.names
            if alias.name == "specs"
        }
    if node.module == "specs":
        return {f"from {'.' * node.level}specs import ..."}
    return set()


def _forbidden_specs_dependencies(module_path: Path) -> set[str]:
    tree = ast.parse(module_path.read_text(encoding="utf-8"))
    targets: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            targets.update(_forbidden_imports_from_import(node))
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            targets.update(_forbidden_imports_from_absolute_from(node))
        elif isinstance(node, ast.ImportFrom):
            targets.update(_forbidden_imports_from_relative_from(node))
    return targets


@pytest.mark.parametrize(
    ("source", "expected_imports"),
    [
        (
            "import engineeringagent.specs\n",
            {"import engineeringagent.specs"},
        ),
        (
            "from engineeringagent import specs\n",
            {"from engineeringagent import specs"},
        ),
        (
            "from engineeringagent.specs import HarnessCheckPhase\n",
            {"from engineeringagent.specs import ..."},
        ),
        (
            "from .. import specs\nfrom ..specs import HarnessCheckPhase\n",
            {"from .. import specs", "from ..specs import ..."},
        ),
    ],
)
def test_forbidden_specs_dependencies_captures_broad_specs_dependency_patterns(
    tmp_path: Path,
    source: str,
    expected_imports: set[str],
) -> None:
    """Import scanning should catch all specs import forms FEAT-178 forbids."""
    module_path = tmp_path / "module.py"
    module_path.write_text(textwrap.dedent(source), encoding="utf-8")

    assert _forbidden_specs_dependencies(module_path) >= expected_imports


def test_cli_and_loop_modules_do_not_depend_on_specs_for_harness_check_phase() -> None:
    """CLI and loop modules should import the checks-owned phase contract directly."""
    repo_root = Path(__file__).resolve().parents[2]
    module_paths = (
        repo_root / "src/engineeringagent/presentation/cli/__init__.py",
        repo_root / "src/engineeringagent/presentation/cli/__main__.py",
        repo_root / "src/engineeringagent/adapters/runtime/iteration_phases.py",
    )

    for module_path in module_paths:
        assert not _forbidden_specs_dependencies(module_path)


def test_cli_and_loop_surfaces_expose_checks_owned_harness_check_phase() -> None:
    """CLI and loop exports should share the checks-owned HarnessCheckPhase object."""
    assert cli_module.HarnessCheckPhase is HarnessCheckPhase
    assert loop_phases.LoopTriggeredChecksRequest.model_fields["phase"].annotation is HarnessCheckPhase
