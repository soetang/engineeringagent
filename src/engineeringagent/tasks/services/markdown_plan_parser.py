"""Parse markdown task plans with YAML frontmatter."""

from pathlib import Path

import yaml

from engineeringagent.tasks.errors import TaskPlanLoadError


class MarkdownPlanParser:
    """Read markdown plans and extract YAML frontmatter."""

    def parse(self, plan_path: str) -> tuple[dict[str, object], str, str]:
        """Return frontmatter data, markdown body, and canonical path."""
        normalized_input = plan_path[1:] if plan_path.startswith("@") else plan_path
        path = Path(normalized_input).expanduser().resolve()
        if path.suffix != ".md":
            raise TaskPlanLoadError(f"Plan path must point to a markdown file: {path}")
        try:
            raw_text = path.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise TaskPlanLoadError(f"Plan file not found: {path}") from exc
        except OSError as exc:
            raise TaskPlanLoadError(f"Failed to read plan file {path}: {exc}") from exc

        frontmatter_text, body = _split_frontmatter(raw_text, str(path))
        try:
            loaded = yaml.safe_load(frontmatter_text)
        except yaml.YAMLError as exc:
            raise TaskPlanLoadError(
                f"Malformed YAML frontmatter in {path}: {exc}"
            ) from exc

        if not isinstance(loaded, dict):
            raise TaskPlanLoadError(
                f"YAML frontmatter in {path} must be a mapping of fields"
            )

        return loaded, body, str(path)


def _split_frontmatter(raw_text: str, plan_path: str) -> tuple[str, str]:
    """Split a markdown document into frontmatter and body."""
    if not raw_text.startswith("---\n") and raw_text != "---":
        raise TaskPlanLoadError(f"Plan file is missing YAML frontmatter: {plan_path}")

    lines = raw_text.splitlines()
    for index, line in enumerate(lines[1:], start=1):
        if line.strip() == "---":
            frontmatter_text = "\n".join(lines[1:index])
            body = "\n".join(lines[index + 1 :])
            if raw_text.endswith("\n"):
                body = f"{body}\n" if body else ""
            return frontmatter_text, body

    raise TaskPlanLoadError(
        f"Plan file is missing the closing YAML frontmatter delimiter: {plan_path}"
    )
