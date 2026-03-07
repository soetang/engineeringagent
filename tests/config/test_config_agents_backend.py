from __future__ import annotations

import sys
from collections.abc import Callable
from pathlib import Path

import pytest

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - Python < 3.11 fallback
    import tomli as tomllib

from engineeringagent.config import (
    DEFAULT_CODEX_PROFILE,
    resolve_agents_backend_id,
    resolve_agents_codex_model,
    resolve_agents_codex_profile,
    resolve_agents_codex_profile_in_engineeringagent_toml,
    write_init_backend_config,
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


def test_agents_backend_returns_unset_when_agents_table_has_no_backend_key(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text("[agents]\n", encoding="utf-8")

    assert resolve_agents_backend_id(tmp_path) is None


def test_agents_backend_returns_unset_when_pyproject_agents_table_has_no_backend_key(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        "[tool.engineeringagent.agents]\n",
        encoding="utf-8",
    )

    assert resolve_agents_backend_id(tmp_path) is None


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


def test_agents_codex_profile_in_engineeringagent_toml_ignores_pyproject(
    tmp_path: Path,
) -> None:
    (tmp_path / "pyproject.toml").write_text(
        '[tool.engineeringagent.agents.codex]\nprofile = "profile.from.pyproject"\n',
        encoding="utf-8",
    )

    assert resolve_agents_codex_profile_in_engineeringagent_toml(tmp_path) is None

    (tmp_path / "engineeringagent.toml").write_text(
        '[agents.codex]\nprofile = "profile.from.engineeringagent"\n',
        encoding="utf-8",
    )

    assert (
        resolve_agents_codex_profile_in_engineeringagent_toml(tmp_path)
        == "profile.from.engineeringagent"
    )


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


def test_write_init_backend_config_persists_codex_profile_for_codex_backend(
    tmp_path: Path,
) -> None:
    created, skipped = write_init_backend_config(
        tmp_path,
        backend_id="codex",
        force=False,
    )

    assert (created, skipped) == (1, 0)
    payload = tomllib.loads(
        (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    )
    assert payload["agents"]["backend"] == "codex"
    assert payload["agents"]["codex"]["profile"] == DEFAULT_CODEX_PROFILE
    assert "model" not in payload["agents"]["codex"]


def test_write_init_backend_config_does_not_persist_codex_profile_for_non_codex_backend(
    tmp_path: Path,
) -> None:
    created, skipped = write_init_backend_config(
        tmp_path,
        backend_id="opencode",
        force=False,
    )

    assert (created, skipped) == (1, 0)
    payload = tomllib.loads(
        (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    )
    assert payload["agents"]["backend"] == "opencode"
    assert "codex" not in payload["agents"]


def test_write_init_backend_config_non_codex_preserves_existing_codex_profile(
    tmp_path: Path,
) -> None:
    (tmp_path / "engineeringagent.toml").write_text(
        '[agents]\nbackend = "codex"\n\n[agents.codex]\nprofile = "custom"\n',
        encoding="utf-8",
    )

    created, skipped = write_init_backend_config(
        tmp_path,
        backend_id="opencode",
        force=True,
    )

    assert (created, skipped) == (1, 0)
    payload = tomllib.loads(
        (tmp_path / "engineeringagent.toml").read_text(encoding="utf-8")
    )
    assert payload["agents"]["backend"] == "opencode"
    assert payload["agents"]["codex"]["profile"] == "custom"
