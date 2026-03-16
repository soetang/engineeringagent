import json
import subprocess
from typing import Optional, Type, TypeVar, Union
from pydantic import BaseModel

from developer.agents.protocol import AgentProtocol

T = TypeVar("T", bound=Union[BaseModel, str])


class VibeAdapter(AgentProtocol):
    """Vibe CLI adapter implementing AgentProtocol."""

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
        if output_format is str:
            return self._run_string_output(prompt, model, profile, path)  # type: ignore[return-value]

        # Handle pydantic model output
        elif issubclass(output_format, BaseModel):
            return self._run_model_output(prompt, output_format, model, profile, path)  # type: ignore[return-value]

        else:
            raise ValueError(f"Unsupported output format: {output_format}")

    def _build_vibe_command(
        self,
        prompt: str,
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
    ) -> list[str]:
        """Build vibe CLI command with common options."""
        cmd = ["vibe", "-p", prompt, "--output", "json"]
        
        if model:
            cmd.extend(["--agent", model])
        
        if path:
            cmd.extend(["--workdir", path])
        
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

    def _run_string_output(
        self,
        prompt: str,
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
    ) -> str:
        """Execute vibe CLI for string output."""
        cmd = self._build_vibe_command(prompt, model, profile, path)

        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            messages = json.loads(result.stdout.strip())
            
            assistant_message = self._extract_assistant_content(messages)
            if assistant_message is not None:
                return assistant_message
            
            if not messages:
                return result.stdout.strip()
            return messages[-1].get("content", result.stdout.strip())
            
        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Vibe CLI failed: {e.stderr}") from e

    def _run_model_output(
        self,
        prompt: str,
        output_format: Type[BaseModel],
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
    ) -> BaseModel:
        """Execute vibe CLI with structured output using JSON schema in prompt."""
        # Generate JSON schema with all fields required
        schema = self._generate_schema(output_format)
        schema_str = json.dumps(schema, indent=2)

        # Prepend schema instructions to the prompt
        full_prompt = (
            f"Return JSON matching this schema:\n"
            f"```json\n"
            f"{schema_str}\n"
            f"```\n\n"
            f"{prompt}"
        )

        # Build command
        cmd = self._build_vibe_command(full_prompt, model, profile, path)

        try:
            # Execute command
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)

            # Parse JSON output
            messages = json.loads(result.stdout.strip())
            
            assistant_message = self._extract_assistant_content(messages)
            if not assistant_message:
                raise RuntimeError("No assistant response found in Vibe output")
            
            # Try to parse the JSON content
            try:
                json_data = self._parse_json_content(assistant_message)
                return output_format(**json_data)
            except json.JSONDecodeError as e:
                raise RuntimeError(f"Failed to parse JSON output: {e}\nContent: {assistant_message}") from e
            except Exception as e:
                raise RuntimeError(f"Failed to create model from output: {e}\nContent: {assistant_message}") from e

        except subprocess.CalledProcessError as e:
            raise RuntimeError(f"Vibe CLI failed: {e.stderr}") from e

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