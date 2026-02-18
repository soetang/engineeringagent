from __future__ import annotations

from pathlib import Path

import pytest

from engineeringagent.config import resolve_agents_backend_id


def test_agents_backend_defaults_to_unset(tmp_path: Path) -> None:
    assert resolve_agents_backend_id(tmp_path) is None


def test_agents_backend_prefers_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "backend.from.engineeringagent"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.agents]\nbackend = "backend.from.pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_agents_backend_id(tmp_path) == "backend.from.engineeringagent"


def test_agents_backend_reads_pyproject_tool_engineeringagent(tmp_path: Path) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.agents]\nbackend = "backend.from.pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_agents_backend_id(tmp_path) == "backend.from.pyproject"


@pytest.mark.parametrize(
    "payload",
    [
        "[agents]\nbackend = 1\n",
        "[agents]\nbackend = true\n",
        '[agents]\nbackend = ""\n',
        '[agents]\nbackend = "   "\n',
    ],
)
def test_agents_backend_rejects_invalid_values(tmp_path: Path, payload: str) -> None:
    (tmp_path / "engineeringagent.toml").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="backend"):
        resolve_agents_backend_id(tmp_path)
