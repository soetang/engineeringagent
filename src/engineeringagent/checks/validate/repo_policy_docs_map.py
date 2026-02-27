from __future__ import annotations

import re
from pathlib import Path

AGENTS_DOCS_MAP_SECTION_TITLE = "Documentation Layout Reference"
AGENTS_PATH = Path("AGENTS.md")

_BACKTICK_TOKEN_PATTERN = re.compile(r"`([^`]+)`")


def append_agents_docs_map_issues(
    messages: list[str],
    *,
    project_root: Path,
    docs_root: Path,
) -> None:
    """Validate AGENTS docs-map references against the active docs root."""

    docs_map_section_line = _agents_docs_map_section_line(project_root)
    docs_map_references = iter_agents_docs_map_references(project_root)
    if docs_map_section_line is not None and not docs_map_references:
        messages.append(
            f"AGENTS.md:{docs_map_section_line}: docs-map section is present but contains no docs/* references"
        )

    for line_number, reference in docs_map_references:
        candidate_references = _docs_map_reference_candidates(
            reference,
            project_root=project_root,
            docs_root=docs_root,
        )
        if _is_glob_reference(reference):
            if any(
                any(project_root.glob(candidate_reference))
                for candidate_reference in candidate_references
            ):
                continue
            messages.append(
                f"AGENTS.md:{line_number}: docs-map glob matches no paths: {reference}"
            )
            continue

        if not any(
            (project_root / candidate_reference).exists()
            for candidate_reference in candidate_references
        ):
            messages.append(
                f"AGENTS.md:{line_number}: docs-map path does not exist: {reference}"
            )


def iter_agents_docs_map_references(project_root: Path) -> list[tuple[int, str]]:
    """Extract documentation map references from AGENTS.md only."""

    agents_path = project_root / AGENTS_PATH
    if not agents_path.exists():
        return []

    lines = agents_path.read_text(encoding="utf-8").splitlines()
    section_start = _find_agents_docs_map_section_start(lines)
    if section_start is None:
        return []

    references: list[tuple[int, str]] = []
    for line_number, line in enumerate(
        lines[section_start + 1 :], start=section_start + 2
    ):
        if line.startswith("## "):
            break
        references.extend((line_number, token) for token in _iter_docs_references(line))

    return sorted(references, key=lambda entry: (entry[0], entry[1]))


def _agents_docs_map_section_line(project_root: Path) -> int | None:
    agents_path = project_root / AGENTS_PATH
    if not agents_path.exists():
        return None

    lines = agents_path.read_text(encoding="utf-8").splitlines()
    section_start = _find_agents_docs_map_section_start(lines)
    if section_start is None:
        return None
    return section_start + 1


def _find_agents_docs_map_section_start(lines: list[str]) -> int | None:
    for index, line in enumerate(lines):
        if _is_agents_docs_map_header(line):
            return index
    return None


def _is_agents_docs_map_header(line: str) -> bool:
    stripped = line.strip()
    if not stripped.startswith("## "):
        return False

    heading = stripped[3:].strip()
    numbered_prefix, separator, remainder = heading.partition(")")
    if separator and numbered_prefix.isdigit():
        heading = remainder.strip()
    return heading == AGENTS_DOCS_MAP_SECTION_TITLE


def _docs_map_reference_candidates(
    reference: str,
    *,
    project_root: Path,
    docs_root: Path,
) -> tuple[str, ...]:
    candidates = [reference]
    if not reference.startswith("docs/"):
        return tuple(candidates)

    default_docs_root = project_root / "docs"
    if docs_root == default_docs_root:
        return tuple(candidates)

    try:
        docs_root_relative = docs_root.relative_to(project_root).as_posix()
    except ValueError:
        return tuple(candidates)

    suffix = reference.removeprefix("docs/")
    mapped_reference = (
        f"{docs_root_relative}/{suffix}" if suffix else docs_root_relative
    )
    if mapped_reference not in candidates:
        candidates.append(mapped_reference)
    return tuple(candidates)


def _iter_docs_references(line: str) -> list[str]:
    return [
        token
        for token in _BACKTICK_TOKEN_PATTERN.findall(line)
        if token.startswith("docs/")
    ]


def _is_glob_reference(reference: str) -> bool:
    return any(char in reference for char in "*?[]")
