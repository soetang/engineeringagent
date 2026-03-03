from __future__ import annotations

from pathlib import Path

APPROACH_AGENTS_BOOTSTRAP_FIXTURE_PATH = "docs/fixtures/approach_bootstrap.md"
APPROACH_AGENTS_BOOTSTRAP_TEXT = (
    Path(__file__).resolve().parents[2] / APPROACH_AGENTS_BOOTSTRAP_FIXTURE_PATH
).read_text(encoding="utf-8").strip()
APPROACH_AGENTS_BOOTSTRAP_LINES = tuple(
    line for line in APPROACH_AGENTS_BOOTSTRAP_TEXT.splitlines() if line.strip()
)

APPROACH_TOPIC_IDS = (
    "overview",
    "principles",
    "workflow",
    "specifications",
    "quality-checks",
    "reviewer-authoring",
)

APPROACH_ALIAS_MAP = {
    "overview": (),
    "principles": ("harness-engineering-principles",),
    "workflow": (),
    "specifications": ("spec-writing",),
    "quality-checks": ("quality-check-playbook",),
    "reviewer-authoring": ("reviewer-authoring-guide",),
}
