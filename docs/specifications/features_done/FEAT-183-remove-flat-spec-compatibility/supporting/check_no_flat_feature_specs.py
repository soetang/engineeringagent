from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]
ACTIVE_FEATURES_DIR = ROOT / "docs/spec/features"
DONE_FEATURES_DIR = ROOT / "docs/spec/features_done"

REFERENCE_CHECKS: dict[str, tuple[str, ...]] = {
    "src/engineeringagent/approach/docs/workflow.md": (
        "docs/spec/features/*.yaml",
        "compatibility wrapper",
    ),
    "src/engineeringagent/approach/docs/specifications.md": (
        "docs/spec/features/*.yaml",
        "compatibility wrapper",
        "legacy wrappers",
    ),
    "src/engineeringagent/approach/docs/reviewer-authoring.md": (
        "compatibility wrapper",
        "legacy wrapper",
    ),
    "docs/references/documentation-practices.md": (
        "docs/spec/features/*.yaml",
        "compatibility wrapper",
        "temporary compatibility wrappers",
    ),
    "harness/reviewers/prompts/intent_integrity_reviewer.md": (
        "docs/spec/features/*.yaml",
        "compatibility wrapper",
    ),
    "harness/reviewers/prompts/test_reviewer.md": (
        "docs/spec/features/*.yaml",
        "compatibility wrapper",
    ),
    "harness/checks.yaml": ("docs/spec/features/*.yaml",),
    "harness/fitness_functions/check_source_first_loop_commands.py": (
        "docs/spec/features/*.yaml",
        "subtasks[*].verification",
    ),
    "harness/fitness_functions/check_real_opencode_hello_world_smoke.py": (
        'feature.get("subtasks")',
        "subtasks",
    ),
}


def _flat_feature_specs(directory: Path) -> list[Path]:
    if not directory.is_dir():
        return []
    return sorted(
        path
        for pattern in ("*.yaml", "*.yml")
        for path in directory.glob(pattern)
        if path.name != "spec.yaml"
    )


def _check_reference_files() -> list[str]:
    violations: list[str] = []
    for relative_path, forbidden_terms in REFERENCE_CHECKS.items():
        path = ROOT / relative_path
        if not path.is_file():
            violations.append(f"missing file: {relative_path}")
            continue
        contents = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in contents:
                violations.append(f"{relative_path}: forbidden term {term!r}")
    return violations


def main() -> int:
    violations: list[str] = []

    for path in _flat_feature_specs(ACTIVE_FEATURES_DIR):
        violations.append(
            f"flat active feature spec still present: {path.relative_to(ROOT)}"
        )
    for path in _flat_feature_specs(DONE_FEATURES_DIR):
        violations.append(
            f"flat archived feature spec still present: {path.relative_to(ROOT)}"
        )

    violations.extend(_check_reference_files())

    if violations:
        sys.stderr.write("Flat feature-spec compatibility remnants detected:\n")
        for violation in violations:
            sys.stderr.write(f"- {violation}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
