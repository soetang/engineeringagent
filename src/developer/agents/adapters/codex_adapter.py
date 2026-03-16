import subprocess
import json
import tempfile
import os
from typing import Optional, Type, TypeVar, Union
from pydantic import BaseModel

from developer.agents.protocol import AgentProtocol

T = TypeVar("T", bound=Union[BaseModel, str])


class CodexAdapter(AgentProtocol):
    """Codex CLI adapter implementing AgentProtocol."""

    def run_agent(
        self,
        prompt: str,
        output_format: Type[T] = str,  # type: ignore[type-arg]
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
    ) -> T:
        """Execute agent with prompt, return structured output or string."""
        # Handle string output (default case)
        if output_format is str or output_format == str:
            return self._run_string_output(prompt, model, profile, path)  # type: ignore[return-value]

        # Handle pydantic model output
        elif issubclass(output_format, BaseModel):
            return self._run_model_output(prompt, output_format, model, profile, path)  # type: ignore[return-value]

        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _build_codex_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
        output_schema: Optional[str] = None,
    ) -> list[str]:
        """Build codex CLI command with common options."""
        cmd = ["codex", "exec", prompt]
        
        if output_schema:
            cmd.extend(["--output-schema", output_schema])
        
        if model:
            cmd.extend(["--model", model])
        
        # Resolve profile to config overrides (checks local config first)
        profile_args = self._resolve_profile_config(profile, path)
        cmd.extend(profile_args)
        
        if path:
            cmd.extend(["--cd", path])
        
        return cmd

    def _run_string_output(
        self,
        prompt: str,
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
    ) -> str:
        """Execute codex CLI for string output."""
        cmd = self._build_codex_command(prompt, model, profile, path)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return result.stdout.strip()
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Codex CLI failed: {e.stderr}") from e

    def _run_model_output(
        self,
        prompt: str,
        output_format: Type[BaseModel],
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
    ) -> BaseModel:
        """Execute codex CLI with structured output using JSON schema."""
        # Generate JSON schema with all fields required (Codex requirement)
        schema = self._generate_schema(output_format)

        # Write schema to temporary file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(schema, f)
            schema_path = f.name

        try:
            # Build command with schema
            cmd = self._build_codex_command(prompt, model, profile, path, schema_path)

            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse JSON output
            try:
                json_data = json.loads(result.stdout.strip())
                return output_format(**json_data)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse JSON output: {e}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to create model from output: {e}") from e

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Codex CLI failed: {e.stderr}") from e
        finally:
            # Clean up temporary schema file
            import os

            try:
                os.unlink(schema_path)
            except:
                pass

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

    def _resolve_profile_config(self, profile: Optional[str] = None, path: Optional[str] = None) -> list:
        """Resolve profile settings to config overrides, checking local config first."""
        if not profile:
            return []
        
        config_overrides = []
        
        # Try to read from local .codex/config.toml first
        local_config_path = ".codex/config.toml"
        if path:
            local_config_path = os.path.join(path, ".codex/config.toml")
        
        try:
            import tomllib
            with open(local_config_path, "rb") as f:
                local_config = tomllib.load(f)
                
            # Check if the profile exists in local config
            if "profiles" in local_config and profile in local_config["profiles"]:
                profile_config = local_config["profiles"][profile]
                
                # Convert profile settings to config overrides
                for key, value in profile_config.items():
                    if isinstance(value, str):
                        config_overrides.extend(["-c", f"{key}=\"{value}\""])
                    else:
                        config_overrides.extend(["-c", f"{key}={value}"])
                
                return config_overrides
        except (FileNotFoundError, ImportError):
            # If local config not found or can't be parsed, fall back to --profile flag
            pass
        
        # Fall back to using --profile flag (will use global config)
        return ["--profile", profile]
