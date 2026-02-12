#!/usr/bin/env python3
from __future__ import annotations

from pathlib import Path

import yaml


def _iter_yaml_files(project_root: Path) -> list[Path]:
    files: list[Path] = []
    for pattern in ("*.yaml", "*.yml"):
        files.extend(project_root.rglob(pattern))
    return sorted(path for path in files if ".git" not in path.parts)


def _validate_yaml(path: Path) -> str | None:
    try:
        with path.open("r", encoding="utf-8") as f:
            yaml.safe_load(f)
    except yaml.YAMLError as exc:
        mark = getattr(exc, "problem_mark", None)
        if mark is not None:
            line = mark.line + 1
            column = mark.column + 1
            return f"{path}:{line}:{column}: invalid YAML: {exc}"
        return f"{path}: invalid YAML: {exc}"
    return None


def main() -> int:
    project_root = Path(__file__).resolve().parents[1]
    errors = [err for path in _iter_yaml_files(project_root) if (err := _validate_yaml(path))]
    if errors:
        for err in errors:
            print(err)
        return 1
    print("yaml validation: ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
