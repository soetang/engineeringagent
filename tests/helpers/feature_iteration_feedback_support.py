from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Callable

import pytest
import yaml

from tests.helpers.feature_iteration_support import install_prompt_capture_agent


def install_stateful_prompt_agent(
    monkeypatch: pytest.MonkeyPatch,
    on_prompt: Callable[[int], None],
) -> list[str]:
    """Capture prompts while delegating state changes to a prompt-index callback."""

    def prompt_handler(
        _prompt: str,
        prompts: list[str],
    ) -> subprocess.CompletedProcess[str]:
        on_prompt(len(prompts))
        return subprocess.CompletedProcess(["opencode"], 0, stdout="ok\n", stderr="")

    return install_prompt_capture_agent(monkeypatch, prompt_handler)


def advance_bundled_plan_prompt_state(
    feature_path: Path,
    plan_path: Path,
    *,
    prompt_count: int,
) -> None:
    """Mark the next bundled phase done for each prompt, then finish the feature."""

    feature = yaml.safe_load(feature_path.read_text(encoding="utf-8"))
    frontmatter, body = _read_plan_frontmatter(plan_path)
    phases = frontmatter.get("phases", [])
    next_phase = _phase_at_index(phases, prompt_count - 1)
    if next_phase is not None:
        next_phase["status"] = "done"
        feature["status"] = "in_progress"
    else:
        feature["status"] = "done"
        frontmatter["status"] = "done"
    feature_path.write_text(yaml.safe_dump(feature, sort_keys=False), encoding="utf-8")
    _write_plan_frontmatter(plan_path, frontmatter, body)


def _phase_at_index(items: object, index: int) -> dict[str, object] | None:
    if not isinstance(items, list) or index < 0 or index >= len(items):
        return None
    item = items[index]
    return item if isinstance(item, dict) else None


def _read_plan_frontmatter(plan_path: Path) -> tuple[dict[str, object], str]:
    document = plan_path.read_text(encoding="utf-8")
    frontmatter_end = document.find("\n---", 4)
    if frontmatter_end == -1:
        raise ValueError(f"Plan markdown is missing closing frontmatter fence: {plan_path}")
    frontmatter = yaml.safe_load(document[4:frontmatter_end])
    if not isinstance(frontmatter, dict):
        raise ValueError(f"Plan frontmatter must be a mapping: {plan_path}")
    return frontmatter, document[frontmatter_end + 4 :]


def _write_plan_frontmatter(
    plan_path: Path,
    frontmatter: dict[str, object],
    body: str,
) -> None:
    plan_path.write_text(
        "---\n" + yaml.safe_dump(frontmatter, sort_keys=False) + "---\n" + body,
        encoding="utf-8",
    )
