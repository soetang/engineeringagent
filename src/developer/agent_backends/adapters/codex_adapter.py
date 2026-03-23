import os
import json
import subprocess
import tempfile
from typing import Optional, Type

from pydantic import BaseModel

from developer.agent_backends.protocol import AgentBackendProtocol, TModel


class CodexAdapter(AgentBackendProtocol):
    """Codex CLI adapter implementing the shared backend contract."""

    def __init__(
        self,
        profile: str | None = None,
        model: str | None = None,
        path: str | None = None,
    ) -> None:
        """Initialize Codex adapter state.

        Args:
            profile: Optional Codex profile name or resolved config preset.
            model: Optional raw Codex model name for ``--model``.
            path: Optional working directory for ``--cd``.
        """
        self.profile = profile
        self.model = model
        self.path = path

    def run_agent(
        self,
        prompt: str,
        output_format: Optional[Type[TModel]] = None,
    ) -> TModel | str:
        """Execute agent with prompt, return structured output or string."""
        # For model output, we need to write schema to temp file
        schema_path = None
        command_prompt = prompt
        if output_format is not None and issubclass(output_format, BaseModel):
            schema = self._generate_schema(output_format)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(schema, f)
                schema_path = f.name
            command_prompt = self._build_structured_prompt(prompt, schema)

        try:
            # Build command
            cmd = self._build_codex_command(
                command_prompt, self.model, self.profile, schema_path
            )

            # Execute command
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            except subprocess.CalledProcessError as e:
                raise RuntimeError(f"Codex CLI failed: {e.stderr}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to execute Codex CLI command: {e}") from e

            # Handle output based on format
            if output_format is None or output_format is str:
                return result.stdout.strip()
            elif issubclass(output_format, BaseModel):
                # Parse JSON output
                try:
                    json_data = self._parse_json_content(result.stdout)
                    return output_format(**json_data)
                except json.JSONDecodeError as e:
                    raise RuntimeError(f"Failed to parse JSON output: {e}") from e
                except Exception as e:
                    raise RuntimeError(
                        f"Failed to create model from output: {e}"
                    ) from e
            else:
                raise ValueError(f"Unsupported output format: {output_format}")

        finally:
            # Clean up temporary schema file
            if schema_path:
                os.unlink(schema_path)

    def _build_codex_command(
        self,
        prompt: str,
        model: str | None = None,
        profile: str | None = None,
        output_schema: str | None = None,
    ) -> list[str]:
        """Build codex CLI command with common options."""
        cmd = ["codex", "exec", prompt]

        if output_schema:
            cmd.extend(["--output-schema", output_schema])

        if model:
            cmd.extend(["--model", model])

        # Resolve profile to config overrides (checks local config first)
        profile_args = self._resolve_profile_config(profile)
        cmd.extend(profile_args)

        if self.path:
            cmd.extend(["--cd", self.path])

        return cmd

    def _build_structured_prompt(self, prompt: str, schema: dict) -> str:
        """Add an explicit JSON-only instruction for structured outputs."""
        schema_str = json.dumps(schema, indent=2)
        return (
            "Return JSON only. Do not include markdown, prose, or code fences.\n"
            "The JSON must match this schema exactly:\n"
            f"{schema_str}\n\n"
            f"{prompt}"
        )

    def _parse_json_content(self, content: str) -> dict:
        """Parse JSON content, tolerating fenced or wrapped JSON responses."""
        clean_content = content.strip()
        if clean_content.startswith("```json") and clean_content.endswith("```"):
            clean_content = "\n".join(clean_content.splitlines()[1:-1]).strip()
        elif clean_content.startswith("```") and clean_content.endswith("```"):
            clean_content = "\n".join(clean_content.splitlines()[1:-1]).strip()

        try:
            return json.loads(clean_content)
        except json.JSONDecodeError:
            decoder = json.JSONDecoder()
            for index, char in enumerate(clean_content):
                if char != "{":
                    continue
                try:
                    parsed, end = decoder.raw_decode(clean_content[index:])
                except json.JSONDecodeError:
                    continue

                trailing = clean_content[index + end :].strip()
                if trailing and trailing != "```":
                    continue
                return parsed

            raise

    def _generate_schema(self, model_class: Type[BaseModel]) -> dict:
        """Generate JSON schema with all fields required for Codex."""
        # Get the model schema
        schema = model_class.model_json_schema()

        # Ensure all properties are in required array (Codex requirement)
        if "properties" in schema:
            all_properties = list(schema["properties"].keys())
            schema["required"] = all_properties

        # Set additionalProperties to false
        schema["additionalProperties"] = False

        return schema

    def _resolve_profile_config(self, profile: str | None = None) -> list[str]:
        """Resolve profile settings to config overrides, checking local config first."""
        if not profile:
            return []

        # Try to read from local .codex/config.toml first
        local_config_path = ".codex/config.toml"
        if self.path:
            local_config_path = os.path.join(self.path, ".codex/config.toml")

        try:
            import tomllib

            with open(local_config_path, "rb") as f:
                local_config = tomllib.load(f)

            # Check if the profile exists in local config
            if "profiles" in local_config and profile in local_config["profiles"]:
                profile_config = local_config["profiles"][profile]
                # Convert profile settings to config overrides
                config_overrides = []
                for key, value in profile_config.items():
                    if isinstance(value, str):
                        config_overrides.extend(["-c", f'{key}="{value}"'])
                    else:
                        config_overrides.extend(["-c", f"{key}={value}"])
                return config_overrides
        except (FileNotFoundError, ImportError):
            pass  # Fall back to using --profile flag

        # Fall back to using --profile flag (will use global config)
        return ["--profile", profile]
