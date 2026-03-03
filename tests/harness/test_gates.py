from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

from engineeringagent import changed_paths
from engineeringagent.git import client as git_client


def test_collect_changed_paths_falls_back_when_git_diff_fails(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    def fake_diff(*_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(returncode=1, stdout="", stderr="boom")

    monkeypatch.setattr(git_client, "diff_name_status", fake_diff)

    result = changed_paths.collect_changed_paths(tmp_path)

    assert result.paths == ()
    assert result.run_all is True
    assert result.reason == changed_paths.FALLBACK_CHANGE_DISCOVERY_REASON


def test_collect_changed_paths_parses_rename_and_normalizes_separators(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    # Include an internal blank line (not just trailing newline) so the
    # implementation exercises the `if not line.strip(): continue` branch.
    stdout = "\n".join(
        [
            "A\tsrc\\engineeringagent\\cli.py",
            " ",
            "R100\tsrc\\old.py\tsrc\\new.py",
        ]
    )

    def fake_diff(*_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(git_client, "diff_name_status", fake_diff)

    result = changed_paths.collect_changed_paths(tmp_path)

    assert result.run_all is False
    assert result.reason is None
    assert result.paths == (
        "src/engineeringagent/cli.py",
        "src/new.py",
        "src/old.py",
    )


def test_collect_changed_paths_includes_base_and_head_when_provided(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    captured: dict[str, Any] = {}

    def fake_diff(project_root: Path, *, base: str | None, head: str | None) -> Any:
        captured["cwd"] = project_root
        captured["base"] = base
        captured["head"] = head
        return SimpleNamespace(returncode=0, stdout="A\tsrc/app.py\n", stderr="")

    monkeypatch.setattr(git_client, "diff_name_status", fake_diff)

    result = changed_paths.collect_changed_paths(tmp_path, base="BASE", head="HEAD")

    assert result.run_all is False
    assert result.paths == ("src/app.py",)
    assert captured["cwd"] == tmp_path
    assert captured["base"] == "BASE"
    assert captured["head"] == "HEAD"


def test_collect_changed_paths_falls_back_on_malformed_diff_output(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    stdout = "NOT_A_STATUS_LINE_WITH_TABS\n"

    def fake_diff(*_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(git_client, "diff_name_status", fake_diff)

    result = changed_paths.collect_changed_paths(tmp_path)

    assert result.run_all is True
    assert result.paths == ()
    assert result.reason == changed_paths.FALLBACK_CHANGE_DISCOVERY_REASON


def test_collect_changed_paths_falls_back_on_malformed_rename_record(
    tmp_path: Path,
    monkeypatch: Any,
) -> None:
    stdout = "R100\tsrc/old.py\n"

    def fake_diff(*_args: Any, **_kwargs: Any) -> Any:
        return SimpleNamespace(returncode=0, stdout=stdout, stderr="")

    monkeypatch.setattr(git_client, "diff_name_status", fake_diff)

    result = changed_paths.collect_changed_paths(tmp_path)

    assert result.run_all is True
    assert result.paths == ()
    assert result.reason == changed_paths.FALLBACK_CHANGE_DISCOVERY_REASON
