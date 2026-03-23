"""Repository scaffold assembly and write workflow."""

from pathlib import Path
import tomllib

from developer.scaffolding.filesystem import upsert_text_file, write_file_if_missing
from developer.scaffolding.models import FileWriteResult, InitRequest, InitResult
from developer.scaffolding.templates import AGENTS_MD_SNIPPET, build_scaffold_files


class ScaffoldingService:
    """Create the minimal onboarding scaffold in a repository."""

    def run(self, request: InitRequest, *, base_path: Path) -> InitResult:
        """Generate the requested scaffold files and optional config/docs entries."""
        file_results: list[FileWriteResult] = []

        if request.create_or_update_config:
            file_results.append(
                self._create_or_update_config(
                    base_path, harness_dir=request.harness_dir
                )
            )

        if request.create_or_append_agents_md:
            file_results.append(self._create_or_append_agents_md(base_path, request))

        for scaffold_file in build_scaffold_files(request.harness_dir):
            file_results.append(
                write_file_if_missing(
                    base_path / scaffold_file.path, scaffold_file.content
                )
            )

        return InitResult(
            harness_dir=base_path / request.harness_dir, file_results=file_results
        )

    def _create_or_update_config(
        self,
        base_path: Path,
        *,
        harness_dir: str,
    ) -> FileWriteResult:
        config_path = base_path / "engineeringagent.toml"
        config = {}
        if config_path.exists():
            config = tomllib.loads(config_path.read_text())

        prompts = dict(config.get("prompts", {}))
        prompts.setdefault(
            "implementation_prompt_path",
            f"{harness_dir}/prompts/implementation_prompt.md",
        )
        prompts.setdefault(
            "commit_prompt_path",
            f"{harness_dir}/prompts/commit_message_prompt.md",
        )
        prompts.setdefault(
            "pull_request_prompt_path",
            f"{harness_dir}/prompts/pull_request_prompt.md",
        )
        config["prompts"] = prompts

        quality = dict(config.get("quality", {}))
        quality.setdefault("checks_path", f"{harness_dir}/checks.yaml")
        config["quality"] = quality

        implementation = dict(config.get("implementation", {}))
        implementation.setdefault("max_iterations", 40)
        config["implementation"] = implementation

        serialized = _serialize_toml(config)
        current = config_path.read_text() if config_path.exists() else None
        if current == serialized:
            return FileWriteResult(
                path=config_path,
                status="skipped",
                reason="already configured",
            )
        return upsert_text_file(config_path, serialized)

    def _create_or_append_agents_md(
        self,
        base_path: Path,
        request: InitRequest,
    ) -> FileWriteResult:
        agents_path = base_path / "AGENTS.md"
        snippet = AGENTS_MD_SNIPPET.replace("<harness-dir>", request.harness_dir)

        if not agents_path.exists():
            return upsert_text_file(agents_path, f"# Agent Instructions\n\n{snippet}\n")

        current = agents_path.read_text()
        if "<!-- developer:init:start -->" in current:
            return FileWriteResult(
                path=agents_path,
                status="skipped",
                reason="developer guidance already present",
            )

        separator = "" if current.endswith("\n") else "\n"
        return upsert_text_file(agents_path, f"{current}{separator}\n{snippet}\n")


def _serialize_toml(data: dict[str, object]) -> str:
    """Serialize a simple dict-of-sections TOML document."""
    lines: list[str] = []
    for section, values in data.items():
        lines.append(f"[{section}]")
        if not isinstance(values, dict):
            raise TypeError(f"Unsupported TOML section value for {section}")
        for key, value in values.items():
            lines.append(f"{key} = {_toml_value(value)}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def _toml_value(value: object) -> str:
    """Serialize a TOML scalar or flat array."""
    if isinstance(value, str):
        escaped = value.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return str(value)
    if isinstance(value, list):
        return "[" + ", ".join(_toml_value(item) for item in value) + "]"
    raise TypeError(f"Unsupported TOML value: {value!r}")
