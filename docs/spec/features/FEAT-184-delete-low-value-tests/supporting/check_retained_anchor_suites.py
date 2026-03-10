from __future__ import annotations

from _cleanup_checks import RETAINED_ANCHORS, missing_files, report_and_exit


def main() -> int:
    violations = missing_files(RETAINED_ANCHORS)
    return report_and_exit("Behavior-facing anchor suites missing", violations)


if __name__ == "__main__":
    raise SystemExit(main())
