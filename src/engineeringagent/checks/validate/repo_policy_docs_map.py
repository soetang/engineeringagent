from __future__ import annotations

from importlib.resources import files

from pathlib import Path

AGENTS_PATH = Path("AGENTS.md")
APPROACH_BOOTSTRAP_LINES = tuple(
    line.strip()
    for line in files("engineeringagent.scaffold_templates")
    .joinpath("AGENTS.md")
    .read_text(encoding="utf-8")
    .splitlines()
    if line.strip()
)
APPROACH_BOOTSTRAP_LINE_SET = frozenset(APPROACH_BOOTSTRAP_LINES)


def _read_agents_lines(agents_path: Path) -> list[str]:
    return agents_path.read_text(encoding="utf-8").splitlines()


def _extract_bootstrap_lines(
    lines: list[str],
) -> set[str]:
    found: set[str] = set()
    for line in lines:
        token = line.strip()
        if token not in APPROACH_BOOTSTRAP_LINE_SET:
            continue
        found.add(token)
    return found


def append_agents_docs_map_issues(
    messages: list[str],
    *,
    project_root: Path,
) -> None:
    """Validate AGENTS guidance bootstrap contract."""
    agents_path = project_root / AGENTS_PATH
    if not agents_path.exists():
        return

    present_lines = _extract_bootstrap_lines(_read_agents_lines(agents_path))
    for expected in APPROACH_BOOTSTRAP_LINES:
        if expected not in present_lines:
            messages.append(
                f"AGENTS.md:1: AGENTS docs bootstrap contract missing required line: {expected}"
            )


def iter_agents_docs_map_references(project_root: Path) -> list[tuple[int, str]]:
    """Extract recognized AGENTS guidance bootstrap lines."""

    agents_path = project_root / AGENTS_PATH
    if not agents_path.exists():
        return []

    found: set[str] = set()
    references: list[tuple[int, str]] = []
    for line_number, line in enumerate(_read_agents_lines(agents_path), start=1):
        token = line.strip()
        if token not in APPROACH_BOOTSTRAP_LINE_SET or token in found:
            continue
        found.add(token)
        references.append((line_number, token))
    return references
