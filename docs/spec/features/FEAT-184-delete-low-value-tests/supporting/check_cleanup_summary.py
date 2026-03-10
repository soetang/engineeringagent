from __future__ import annotations

from _cleanup_checks import (
    COVERAGE_CONTRACT_TERMS,
    HELPER_PADDING_TARGETS,
    LOOP_TRIM_TARGETS,
    RETAINED_ANCHORS,
    WAVE1_DELETE_TARGETS,
    missing_files,
    missing_terms,
    present_files,
    report_and_exit,
)


def main() -> int:
    violations = present_files(
        WAVE1_DELETE_TARGETS + HELPER_PADDING_TARGETS + LOOP_TRIM_TARGETS
    )
    violations.extend(
        f"retained anchor missing: {path}" for path in missing_files(RETAINED_ANCHORS)
    )
    violations.extend(missing_terms(COVERAGE_CONTRACT_TERMS))
    return report_and_exit("FEAT-184 cleanup summary checks failed", violations)


if __name__ == "__main__":
    raise SystemExit(main())
