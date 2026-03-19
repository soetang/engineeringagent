import json
import subprocess
from typing import Optional, Type

from pydantic import BaseModel

from developer.agent_backends.protocol import AgentBackendProtocol, TModel


class VibeAdapter(AgentBackendProtocol):
    """Vibe CLI adapter mapping shared profile semantics to ``vibe --agent``."""

    def __init__(
        self,
        profile: str | None = None,
        model: str | None = None,
        path: str | None = None,
    ) -> None:
        """Initialize Vibe adapter state.

        Args:
            profile: Optional Vibe agent profile passed through ``--agent``.
            model: Unsupported for Vibe. Use ``profile`` instead.
            path: Optional working directory for ``--workdir``.

        Raises:
            ValueError: If ``model`` is provided for the Vibe backend.
        """
        if model is not None:
            raise ValueError(
                "Vibe backend does not support `model`; use `profile` to select a Vibe agent."
            )

        self.profile = profile
        self.model = None
        self.path = path

    def run_agent(
        self,
        prompt: str,
        output_format: Optional[Type[TModel]] = None,
    ) -> TModel | str:
        """Execute agent with prompt, return structured output or string."""
        # Build and execute command

        # For model output, we need to include schema in the prompt
        if output_format is not None and issubclass(output_format, BaseModel):
            schema = self._generate_schema(output_format)
            schema_str = json.dumps(schema, indent=2)
            full_prompt = f"Return JSON matching this schema:\n```json\n{schema_str}\n```\n\n{prompt}"
            cmd = self._build_vibe_command(full_prompt)
        else:
            cmd = self._build_vibe_command(prompt)

        # Execute subprocess command
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Vibe CLI failed: {e.stderr}") from e
        except Exception as e:
            raise RuntimeError(f"Failed to execute Vibe CLI command: {e}") from e

        # Parse JSON output from subprocess
        try:
            messages = json.loads(result.stdout.strip())
        except json.JSONDecodeError as e:
            raise RuntimeError(f"Failed to parse Vibe CLI JSON output: {e}") from e
        except Exception as e:
            raise RuntimeError(f"Unexpected error parsing Vibe output: {e}") from e

        # Extract content from messages
        try:
            assistant_message = self._extract_assistant_content(messages)
            if assistant_message is None:
                if not messages:
                    content = result.stdout.strip()
                else:
                    content = messages[-1].get("content", result.stdout.strip())
            else:
                content = assistant_message
        except Exception as e:
            raise RuntimeError(
                f"Failed to extract content from Vibe messages: {e}"
            ) from e

        # Handle output based on format
        if output_format is None or output_format is str:
            return content
        elif issubclass(output_format, BaseModel):
            # Parse JSON content and create model instance
            try:
                json_data = self._parse_json_content(content)
                return output_format(**json_data)
            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"Failed to parse JSON output: {e}\nContent: {content}"
                ) from e
            except Exception as e:
                raise RuntimeError(
                    f"Failed to create model from output: {e}\nContent: {content}"
                ) from e
        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _build_vibe_command(
        self,
        prompt: str,
    ) -> list[str]:
        """Build vibe CLI command with common options."""
        cmd = ["vibe", "-p", prompt, "--output", "json"]

        if self.profile:
            cmd.extend(["--agent", self.profile])

        if self.path:
            cmd.extend(["--workdir", self.path])

        return cmd

    def _extract_assistant_content(self, messages: list[dict]) -> str | None:
        """Extract assistant content from messages, returning None if not found."""
        for message in reversed(messages):
            if message.get("role") == "assistant" and message.get("content"):
                return message["content"]
        return None

    def _parse_json_content(self, content: str) -> dict:
        """Parse JSON content, handling markdown code blocks."""
        clean_content = content.strip()
        if clean_content.startswith("```json") and clean_content.endswith("```"):
            clean_content = "\n".join(clean_content.splitlines()[1:-1]).strip()
        return json.loads(clean_content)

    def _generate_schema(self, model_class: Type[BaseModel]) -> dict:
        """Generate JSON schema with all fields required for Vibe."""
        # Get the model schema
        schema = model_class.model_json_schema()

        # Ensure all properties are in required array
        if "properties" in schema:
            all_properties = list(schema["properties"].keys())
            schema["required"] = all_properties

        # Set additionalProperties to false
        schema["additionalProperties"] = False

        return schema
