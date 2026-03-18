import os
import subprocess
import tempfile
import json
from typing import Optional, Type, TypeVar

from pydantic import BaseModel

from developer.agents.protocol import AgentProtocol, TModel


class CodexAdapter(AgentProtocol):
    """Codex CLI adapter implementing AgentProtocol."""

    def __init__(
        self,
        profile: Optional[str] = None,
        model: Optional[str] = None,
        path: Optional[str] = None,
    ):
        """Initialize Codex adapter with profile and model configuration."""
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
        if output_format is not None and issubclass(output_format, BaseModel):
            schema = self._generate_schema(output_format)
            with tempfile.NamedTemporaryFile(
                mode="w", suffix=".json", delete=False
            ) as f:
                json.dump(schema, f)
                schema_path = f.name

        try:
            # Build command
            cmd = self._build_codex_command(
                prompt, self.model, self.profile, schema_path
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
                    json_data = json.loads(result.stdout.strip())
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
        model: Optional[str] = None,
        profile: Optional[str] = None,
        output_schema: Optional[str] = None,
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

    def _resolve_profile_config(self, profile: Optional[str] = None) -> list:
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
