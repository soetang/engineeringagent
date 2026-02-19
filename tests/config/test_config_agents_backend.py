from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from engineeringagent.config import (
    resolve_agents_backend_id,
    resolve_agents_codex_model,
    resolve_agents_codex_profile,
)


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


def test_agents_codex_options_default_to_unset(tmp_path: Path) -> None:
    assert resolve_agents_codex_profile(tmp_path) is None
    assert resolve_agents_codex_model(tmp_path) is None


def test_agents_codex_options_prefer_engineeringagent_toml_over_pyproject(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents.codex]\nprofile = "profile.from.engineeringagent"\nmodel = "model.from.engineeringagent"\n',
        encoding="utf-8",
    )
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.agents.codex]\nprofile = "profile.from.pyproject"\nmodel = "model.from.pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_agents_codex_profile(tmp_path) == "profile.from.engineeringagent"
    assert resolve_agents_codex_model(tmp_path) == "model.from.engineeringagent"


@pytest.mark.parametrize(
    ("payload", "expected_profile", "expected_model"),
    [
        (
            '[tool.engineeringagent.agents.codex]\nprofile = "profile.from.pyproject"\n',
            "profile.from.pyproject",
            None,
        ),
        (
            '[tool.engineeringagent.agents.codex]\nmodel = "model.from.pyproject"\n',
            None,
            "model.from.pyproject",
        ),
    ],
)
def test_agents_codex_options_read_pyproject_when_engineeringagent_unset(
    tmp_path: Path,
    payload: str,
    expected_profile: str | None,
    expected_model: str | None,
) -> None:
    (tmp_path / "pyproject.toml").write_text(payload, encoding="utf-8")

    assert resolve_agents_codex_profile(tmp_path) == expected_profile
    assert resolve_agents_codex_model(tmp_path) == expected_model


@pytest.mark.parametrize(
    ("payload", "resolver"),
    [
        ("[agents.codex]\nprofile = 1\n", resolve_agents_codex_profile),
        ("[agents.codex]\nprofile = true\n", resolve_agents_codex_profile),
        ('[agents.codex]\nprofile = ""\n', resolve_agents_codex_profile),
        ('[agents.codex]\nprofile = "   "\n', resolve_agents_codex_profile),
        ("[agents.codex]\nmodel = 1\n", resolve_agents_codex_model),
        ("[agents.codex]\nmodel = false\n", resolve_agents_codex_model),
        ('[agents.codex]\nmodel = ""\n', resolve_agents_codex_model),
        ('[agents.codex]\nmodel = "   "\n', resolve_agents_codex_model),
    ],
)
def test_agents_codex_options_reject_invalid_values(
    tmp_path: Path,
    payload: str,
    resolver: Callable[[Path], str | None],
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(payload, encoding="utf-8")

    with pytest.raises(ValueError, match="agents.codex"):
        resolver(tmp_path)
