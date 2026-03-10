from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]

WAVE1_DELETE_TARGETS = (
    "tests/meta/test_legacy_shim_imports.py",
    "tests/meta/test_no_gate_profile_references.py",
    "tests/meta/test_legacy_checks_import_guard.py",
    "tests/meta/test_agent_boundary_guards.py",
    "tests/meta/test_agent_boundary_migration_smoke.py",
    "tests/specs/test_specs_layout_smoke.py",
    "tests/fitness/test_fitness_rules_repo_validators_boundary.py",
    "tests/fitness/test_fitness_rules_test_layout_module_mirroring.py",
    "tests/fitness/test_fitness_rules_no_doc_content_tests.py",
    "tests/fitness/test_fitness_rules_source_first_loop_commands.py",
    "tests/fitness/test_fitness_rules_harness_src_import_allowlist.py",
    "tests/fitness/test_fitness_rules_scaffold_template_locality.py",
)

HELPER_PADDING_TARGETS = (
    "tests/meta/test_coverage_threshold_regressions.py",
    "tests/meta/test_coverage_misc.py",
)

LOOP_TRIM_TARGETS = (
    "tests/loop/test_loop_feature_iteration_support.py",
    "tests/loop/test_feature_iteration_feedback_support.py",
    "tests/loop/test_loop_feature_phase_progress_helpers.py",
    "tests/loop/test_selected_feature_load_without_archive_fallback.py",
)

RETAINED_ANCHORS = (
    "tests/meta/test_validator.py",
    "tests/checks/test_run_checks_contract_loader.py",
    "tests/cli/test_cli.py",
    "tests/config/test_config_agents_backend.py",
    "tests/agents/test_opencode_backend.py",
    "tests/agents/test_codex_backend.py",
    "tests/git/test_client.py",
    "tests/git/test_git_client.py",
    "tests/loop/test_loop_feature_iteration_lifecycle.py",
    "tests/loop/test_loop_feature_iteration_execution.py",
    "tests/loop/test_loop_feature_iteration_verification.py",
    "tests/loop/test_loop_reviewers.py",
    "tests/loop/test_loop_runtime_iteration.py",
    "tests/loop/test_loop_opencode_integration.py",
)

COVERAGE_CONTRACT_TERMS: dict[str, tuple[str, ...]] = {
    "pyproject.toml": (
        "--cov=engineeringagent",
        "--cov-fail-under=95",
    ),
    "harness/checks.yaml": ("uv run pytest -q",),
    "tests/meta/test_validator.py": (
        "--cov=engineeringagent",
        "--cov-fail-under=95",
    ),
}


def _relative_paths(paths: tuple[str, ...]) -> list[Path]:
    return [ROOT / relative_path for relative_path in paths]


def missing_files(paths: tuple[str, ...]) -> list[str]:
    return [
        relative_path
        for relative_path, path in zip(paths, _relative_paths(paths))
        if not path.is_file()
    ]


def present_files(paths: tuple[str, ...]) -> list[str]:
    return [
        relative_path
        for relative_path, path in zip(paths, _relative_paths(paths))
        if path.exists()
    ]


def missing_terms(checks: dict[str, tuple[str, ...]]) -> list[str]:
    violations: list[str] = []
    for relative_path, required_terms in checks.items():
        path = ROOT / relative_path
        if not path.is_file():
            violations.append(f"missing file: {relative_path}")
            continue
        contents = path.read_text(encoding="utf-8")
        for term in required_terms:
            if term not in contents:
                violations.append(f"{relative_path}: missing required term {term!r}")
    return violations


def report_and_exit(header: str, violations: list[str]) -> int:
    if not violations:
        return 0
    sys.stderr.write(f"{header}:\n")
    for violation in violations:
        sys.stderr.write(f"- {violation}\n")
    return 1
