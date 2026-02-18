from __future__ import annotations

from functools import lru_cache

import pathspec


def _normalize_path(path: str) -> str:
    normalized = path.replace("\\", "/")
    if normalized.startswith("./"):
        normalized = normalized[2:]
    return normalized.lstrip("/")


def _normalize_patterns(patterns: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(pattern.replace("\\", "/") for pattern in patterns)


@lru_cache(maxsize=256)
def _compile_spec(patterns: tuple[str, ...]) -> pathspec.PathSpec:
    return pathspec.PathSpec.from_lines("gitignore", _normalize_patterns(patterns))


def path_matches_any_glob(path: str, patterns: list[str]) -> bool:
    """Return whether a repository-relative path matches any configured glob."""
    if not patterns:
        return False
    return _compile_spec(tuple(patterns)).match_file(_normalize_path(path))
