from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]
REGISTRY_PATH = ROOT / "src/engineeringagent/approach/registry.py"

PACKAGED_DOCS = (
    ROOT / "src/engineeringagent/approach/docs/research-session.md",
    ROOT / "src/engineeringagent/approach/docs/plan-session.md",
)

FORBIDDEN_REGISTRY_TERMS = (
    "_REPO_APPROACH_DOCS",
    "_iter_repo_approach_topics",
    "docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/research-session-approach.md",
    "docs/spec/features_done/FEAT-181-bundled-feature-planning-workflow/supporting/plan-session-approach.md",
    'source="repo"',
)


def main() -> int:
    violations: list[str] = []

    for path in PACKAGED_DOCS:
        if not path.is_file():
            violations.append(
                f"missing packaged approach doc: {path.relative_to(ROOT)}"
            )

    if not REGISTRY_PATH.is_file():
        violations.append(f"missing registry file: {REGISTRY_PATH.relative_to(ROOT)}")
    else:
        contents = REGISTRY_PATH.read_text(encoding="utf-8")
        for term in FORBIDDEN_REGISTRY_TERMS:
            if term in contents:
                violations.append(
                    f"src/engineeringagent/approach/registry.py: forbidden term {term!r}"
                )

    if violations:
        sys.stderr.write("Repo-backed approach wrapper remnants detected:\n")
        for violation in violations:
            sys.stderr.write(f"- {violation}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
