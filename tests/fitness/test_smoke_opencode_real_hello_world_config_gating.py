from __future__ import annotations

import importlib.util
import json
from pathlib import Path


def _load_smoke_module(repo_root: Path):
    smoke_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "check_real_opencode_hello_world_smoke.py"
    )
    spec = importlib.util.spec_from_file_location(
        "engineeringagent_tests.real_opencode_smoke",
        smoke_path,
    )
    assert spec is not None
    assert spec.loader is not None

    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _set_smoke_repo_root(*, smoke, repo_root: Path, monkeypatch) -> None:
    smoke_path = (
        repo_root
        / "harness"
        / "fitness_functions"
        / "check_real_opencode_hello_world_smoke.py"
    )
    monkeypatch.setattr(smoke, "__file__", str(smoke_path))


def test_smoke_rule_skips_when_disabled_in_toml(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch,
    capsys,
) -> None:
    smoke = _load_smoke_module(repo_root)

    fake_repo_root = tmp_path / "fake_repo"
    _set_smoke_repo_root(smoke=smoke, repo_root=fake_repo_root, monkeypatch=monkeypatch)

    cwd_root = tmp_path / "cwd"
    cwd_root.mkdir(parents=True, exist_ok=True)
    (cwd_root / "engineeringagent.toml").write_text(
        "[harness.fitness]\nopencode-real-smoke = true\n",
        encoding="utf-8",
    )

    monkeypatch.chdir(cwd_root)
    monkeypatch.setattr(smoke.shutil, "which", lambda *_args, **_kwargs: None)

    exit_code = smoke.main()
    assert exit_code == 0

    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert payload["status"] == "pass"
    assert payload["summary"] == "skipped (disabled in engineeringagent.toml)"


def test_smoke_rule_fails_when_enabled_but_opencode_missing(
    tmp_path: Path,
    repo_root: Path,
    monkeypatch,
    capsys,
) -> None:
    smoke = _load_smoke_module(repo_root)

    fake_repo_root = tmp_path / "fake_repo"
    fake_repo_root.mkdir(parents=True, exist_ok=True)
    (fake_repo_root / "engineeringagent.toml").write_text(
        "[harness.fitness]\nopencode-real-smoke = true\n",
        encoding="utf-8",
    )

    _set_smoke_repo_root(smoke=smoke, repo_root=fake_repo_root, monkeypatch=monkeypatch)

    cwd_root = tmp_path / "cwd"
    cwd_root.mkdir(parents=True, exist_ok=True)

    monkeypatch.chdir(cwd_root)
    monkeypatch.setattr(smoke.shutil, "which", lambda *_args, **_kwargs: None)

    exit_code = smoke.main()
    assert exit_code == 0

    captured = capsys.readouterr().out.strip()
    payload = json.loads(captured)
    assert payload["status"] == "fail"
    assert "opencode" in payload["summary"].lower()
    assert any(
        "engineeringagent.toml" in entry for entry in payload.get("violations", [])
    )
