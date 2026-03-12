from __future__ import annotations

from _cleanup_checks import (
    COVERAGE_CONTRACT_TERMS,
    HELPER_PADDING_TARGETS,
    RETAINED_ANCHORS,
    missing_files,
    missing_terms,
    present_files,
    report_and_exit,
)


def main() -> int:
    violations = present_files(HELPER_PADDING_TARGETS)
    violations.extend(missing_terms(COVERAGE_CONTRACT_TERMS))
    violations.extend(
        f"retained anchor missing: {path}" for path in missing_files(RETAINED_ANCHORS)
    )
    return report_and_exit("Wave 2 anchor and coverage checks failed", violations)


if __name__ == "__main__":
    raise SystemExit(main())
