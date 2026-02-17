from __future__ import annotations

from pathlib import Path

from engineeringagent.fitness.contracts import (
    CONTRACT_VERSION,
    FitnessRuleResult,
    RuleSeverity,
    RuleStatus,
)
from engineeringagent.fitness.envelope import emit_result_envelope


RULE_ID = "architecture.markdown-locality-reference-coverage"

_MARKDOWN_ALLOWED_ROOTS = (
    Path("docs"),
    Path("harness/reviewers/prompts"),
    Path("src/engineeringagent/prompts"),
    Path("src/engineeringagent/scaffold_templates"),
)
_MARKDOWN_ALLOWED_ROOT_FILES = (
    Path("README.md"),
    Path("AGENTS.md"),
)
_MARKDOWN_REFERENCE_SCAN_SUFFIXES = {
    ".cfg",
    ".ini",
    ".json",
    ".jsonl",
    ".md",
    ".py",
    ".toml",
    ".txt",
    ".yaml",
    ".yml",
}
_MARKDOWN_IGNORE_DIRECTORIES = {
    ".git",
    ".opencode",
    ".pytest_cache",
    ".ruff_cache",
    ".venv",
    "__pycache__",
    "dist",
    "node_modules",
    "output",
    "tmp",
}
_MARKDOWN_LOCALITY_REMEDIATION = (
    "move markdown files under docs/, harness/reviewers/prompts/, "
    "src/engineeringagent/prompts/, or src/engineeringagent/scaffold_templates/; "
    "only repository-root README.md and AGENTS.md are exempt from locality "
    "restrictions."
)


def _path_contains_ignored_directory(relative_path: Path) -> bool:
    return any(part in _MARKDOWN_IGNORE_DIRECTORIES for part in relative_path.parts)


def _iter_markdown_files(project_root: Path) -> list[Path]:
    markdown_paths: list[Path] = []
    for path in sorted(project_root.rglob("*.md")):
        relative = path.relative_to(project_root)
        if _path_contains_ignored_directory(relative):
            continue
        markdown_paths.append(relative)
    return markdown_paths


def _is_allowed_markdown_locality(relative_path: Path) -> bool:
    if relative_path in _MARKDOWN_ALLOWED_ROOT_FILES:
        return True
    return any(
        relative_path == allowed_root or allowed_root in relative_path.parents
        for allowed_root in _MARKDOWN_ALLOWED_ROOTS
    )


def _is_outside_docs(relative_path: Path) -> bool:
    return relative_path != Path("docs") and Path("docs") not in relative_path.parents


def _markdown_reference_patterns(markdown_path: Path) -> tuple[str, ...]:
    posix = markdown_path.as_posix()
    return (
        posix,
        f"./{posix}",
    )


def _iter_reference_scan_files(project_root: Path) -> list[Path]:
    scan_paths: list[Path] = []
    for path in sorted(project_root.rglob("*")):
        if not path.is_file():
            continue
        relative = path.relative_to(project_root)
        if _path_contains_ignored_directory(relative):
            continue
        if path.suffix not in _MARKDOWN_REFERENCE_SCAN_SUFFIXES:
            continue
        scan_paths.append(relative)
    return scan_paths


def _collect_markdown_references(
    project_root: Path,
    markdown_paths: list[Path],
) -> dict[Path, list[str]]:
    references: dict[Path, list[str]] = {path: [] for path in markdown_paths}
    patterns_by_path = {
        path: _markdown_reference_patterns(path) for path in markdown_paths
    }

    for scan_relative in _iter_reference_scan_files(project_root):
        scan_path = project_root / scan_relative
        try:
            content = scan_path.read_text(encoding="utf-8")
        except (OSError, UnicodeDecodeError):
            continue

        for line_number, line in enumerate(content.splitlines(), start=1):
            for markdown_path, patterns in patterns_by_path.items():
                if scan_relative == markdown_path:
                    continue
                if any(pattern in line for pattern in patterns):
                    references[markdown_path].append(f"{scan_relative}:{line_number}")

    return references


def _markdown_locality_reference_coverage_violations(project_root: Path) -> list[str]:
    violations: list[str] = []
    markdown_paths = _iter_markdown_files(project_root)
    for relative_path in markdown_paths:
        if _is_allowed_markdown_locality(relative_path):
            continue
        violations.append(
            f"{relative_path}:1 markdown file is outside approved locality roots; "
            f"{_MARKDOWN_LOCALITY_REMEDIATION}"
        )

    references_by_markdown = _collect_markdown_references(project_root, markdown_paths)
    for relative_path in markdown_paths:
        if not _is_outside_docs(relative_path):
            continue
        if references_by_markdown.get(relative_path):
            continue
        violations.append(
            f"{relative_path}:1 markdown file outside docs/ has no in-repo non-self "
            "reference; add at least one deterministic path reference from another "
            "repository file."
        )

    return sorted(violations)


def main() -> int:
    violations = _markdown_locality_reference_coverage_violations(Path("."))
    status = RuleStatus.PASS if not violations else RuleStatus.FAIL
    summary = (
        "Markdown locality and reference coverage constraints satisfied."
        if status == RuleStatus.PASS
        else f"Detected {len(violations)} markdown locality/reference violation(s)."
    )

    emit_result_envelope(
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
