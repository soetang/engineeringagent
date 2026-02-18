from __future__ import annotations

from importlib.resources import files
from string import Template

_SCAFFOLD_TEMPLATE_PACKAGE = (
    "engineeringagent.agents.backends.opencode.scaffold_templates"
)


def _render_template(
    template_name: str,
    substitutions: dict[str, str] | None = None,
) -> str:
    """Render an OpenCode backend scaffold template asset."""
    template_text = (
        files(_SCAFFOLD_TEMPLATE_PACKAGE)
        .joinpath(template_name)
        .read_text(encoding="utf-8")
    )
    if substitutions is None:
        return template_text
    return Template(template_text).substitute(substitutions)


def build_opencode_scaffold_manifest(agent_model: str) -> dict[str, str]:
    """Build OpenCode-owned scaffold files for init output."""
    return {
        ".opencode/agents/engineeringagent.md": _render_template(
            "agent.engineeringagent.template",
            substitutions={"agent_model": agent_model},
        ),
        ".opencode/.gitignore": _render_template("gitignore"),
    }
