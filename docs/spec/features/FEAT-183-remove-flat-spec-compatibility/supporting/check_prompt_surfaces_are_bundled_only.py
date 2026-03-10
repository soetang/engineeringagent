from __future__ import annotations

from pathlib import Path
import sys


ROOT = Path(__file__).resolve().parents[5]

CHECKS: dict[str, tuple[str, ...]] = {
    "src/engineeringagent/application/prompt_builder.py": (
        "compatibility wrapper",
        "compatibility-wrapper",
        "canonical bundled package",
    ),
    "harness/reviewers/prompts/intent_integrity_reviewer.md": (
        "compatibility wrapper",
        "compatibility-wrapper",
        "docs/spec/features/*.yaml",
    ),
    "harness/reviewers/prompts/test_reviewer.md": (
        "compatibility wrapper",
        "compatibility-wrapper",
        "docs/spec/features/*.yaml",
    ),
}


def main() -> int:
    """Fail when prompt-facing files mention retired flat-spec guidance."""

    violations: list[str] = []
    for relative_path, forbidden_terms in CHECKS.items():
        path = ROOT / relative_path
        if not path.is_file():
            violations.append(f"missing file: {relative_path}")
            continue
        contents = path.read_text(encoding="utf-8")
        for term in forbidden_terms:
            if term in contents:
                violations.append(f"{relative_path}: forbidden term {term!r}")

    if violations:
        sys.stderr.write("Prompt surfaces still mention retired flat-spec guidance:\n")
        for violation in violations:
            sys.stderr.write(f"- {violation}\n")
        return 1

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
