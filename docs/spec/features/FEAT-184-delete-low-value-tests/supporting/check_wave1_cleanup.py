from __future__ import annotations

from _cleanup_checks import (
    RETAINED_ANCHORS,
    WAVE1_DELETE_TARGETS,
    missing_files,
    present_files,
    report_and_exit,
)


def main() -> int:
    violations = present_files(WAVE1_DELETE_TARGETS)
    violations.extend(
        f"retained anchor missing: {path}" for path in missing_files(RETAINED_ANCHORS)
    )
    return report_and_exit("Wave 1 cleanup is incomplete", violations)


if __name__ == "__main__":
    raise SystemExit(main())
