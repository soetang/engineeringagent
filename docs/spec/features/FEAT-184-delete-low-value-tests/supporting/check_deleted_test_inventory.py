from __future__ import annotations

from _cleanup_checks import (
    HELPER_PADDING_TARGETS,
    LOOP_TRIM_TARGETS,
    WAVE1_DELETE_TARGETS,
    present_files,
    report_and_exit,
)


def main() -> int:
    violations = present_files(
        WAVE1_DELETE_TARGETS + HELPER_PADDING_TARGETS + LOOP_TRIM_TARGETS
    )
    return report_and_exit("Low-value test inventory still present", violations)


if __name__ == "__main__":
    raise SystemExit(main())
