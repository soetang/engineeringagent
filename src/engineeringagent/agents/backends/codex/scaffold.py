from __future__ import annotations

from importlib.resources import files
from string import Template

from .model_ids import normalize_codex_model_id

_SCAFFOLD_TEMPLATE_PACKAGE = "engineeringagent.agents.backends.codex.scaffold_templates"


def _render_template(
    template_name: str,
    substitutions: dict[str, str] | None = None,
) -> str:
    """Render a Codex backend scaffold template asset."""
    template_text = (
        files(_SCAFFOLD_TEMPLATE_PACKAGE)
        .joinpath(template_name)
        .read_text(encoding="utf-8")
    )
    if substitutions is None:
        return template_text
    return Template(template_text).substitute(substitutions)


def build_codex_scaffold_manifest(agent_model: str) -> dict[str, str]:
    """Build Codex-owned scaffold files for init output."""
    return {
        ".codex/config.toml": _render_template(
            "config.toml",
            substitutions={"agent_model": normalize_codex_model_id(agent_model)},
        ),
    }
