"""Real integration tests for Codex CLI adapter."""

import json
import subprocess
from pathlib import Path
from shutil import copytree

import pytest
from pydantic import BaseModel

from developer.agent_backends.adapters.codex_adapter import CodexAdapter


class MathResult(BaseModel):
    """Model for math operation results."""

    result: int
    operation: str
    success: bool = True


class FileListResult(BaseModel):
    """Model for file listing results."""

    files: list[str]
    count: int
    path: str = "."


class SimpleResult(BaseModel):
    """Simple model with single field."""

    answer: str


def test_build_codex_command_maps_model_profile_and_path(monkeypatch, tmp_path):
    """Codex command building should preserve shared model/profile/path semantics."""
    adapter = CodexAdapter(
        model="gpt-5.3-codex-spark",
        profile="implementation",
        path=str(tmp_path),
    )
    monkeypatch.setattr(
        adapter,
        "_resolve_profile_config",
        lambda profile: ["--profile", profile] if profile else [],
    )

    command = adapter._build_codex_command(
        prompt="Solve the task",
        model=adapter.model,
        profile=adapter.profile,
    )

    assert command == [
        "codex",
        "exec",
        "Solve the task",
        "--model",
        "gpt-5.3-codex-spark",
        "--profile",
        "implementation",
        "--cd",
        str(tmp_path),
    ]


def test_resolve_profile_config_falls_back_to_profile_flag(tmp_path):
    """Missing local profile config should fall back to the Codex profile flag."""
    adapter = CodexAdapter(path=str(tmp_path))

    assert adapter._resolve_profile_config("implementation") == [
        "--profile",
        "implementation",
    ]


def test_parse_json_content_accepts_fenced_json():
    """Structured parsing should tolerate fenced JSON from Codex."""
    adapter = CodexAdapter()

    parsed = adapter._parse_json_content(
        """```json
{"answer": "Paris"}
```"""
    )

    assert parsed == {"answer": "Paris"}


def test_parse_json_content_extracts_json_from_wrapped_response():
    """Structured parsing should tolerate leading prose before a JSON block."""
    adapter = CodexAdapter()

    parsed = adapter._parse_json_content(
        """Let me analyze the code for simplification opportunities:

```json
{"status": "approved", "summary": "Looks good", "actions": []}
```"""
    )

    assert parsed == {
        "status": "approved",
        "summary": "Looks good",
        "actions": [],
    }


def test_run_agent_adds_structured_prompt_and_parses_fenced_json(monkeypatch):
    """Structured output requests should explicitly demand JSON-only output."""
    adapter = CodexAdapter(model="gpt-5.3-codex-spark")
    captured: dict[str, list[str]] = {}

    def fake_run(cmd, capture_output, text, check):
        captured["cmd"] = cmd
        return subprocess.CompletedProcess(
            args=cmd,
            returncode=0,
            stdout='```json\n{"answer": "Paris"}\n```',
            stderr="",
        )

    monkeypatch.setattr(subprocess, "run", fake_run)

    result = adapter.run_agent(
        prompt="What is the capital of France?",
        output_format=SimpleResult,
    )

    assert result == SimpleResult(answer="Paris")
    prompt_arg = captured["cmd"][2]
    assert "Return JSON only." in prompt_arg
    assert "Do not include markdown, prose, or code fences." in prompt_arg
    assert json.dumps(adapter._generate_schema(SimpleResult), indent=2) in prompt_arg


@pytest.fixture
def temp_stub_dir(tmp_path: Path) -> Path:
    """Fixture that creates a temporary directory with test files and git repo."""
    stub_source = Path(__file__).parent / "stub_data"
    copytree(stub_source, tmp_path, dirs_exist_ok=True)

    subprocess.run(["git", "init"], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "config", "user.email", "test@example.com"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test User"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    subprocess.run(["git", "add", "."], cwd=tmp_path, capture_output=True, check=True)
    subprocess.run(
        ["git", "commit", "-m", "Initial commit"],
        cwd=tmp_path,
        capture_output=True,
        check=True,
    )

    return tmp_path


@pytest.mark.integration
def test_real_string_output():
    """Test real CLI string output."""
    adapter = CodexAdapter(model="gpt-5.3-codex-spark")
    result = adapter.run_agent(
        prompt="What is 2 + 2?",
    )

    assert isinstance(result, str)
    assert result.strip()  # Should not be empty
    # Check for mathematical answer (could be "4", "2+2", "4.0", etc.)
    assert any(char.isdigit() for char in result) or "+" in result


@pytest.mark.integration
def test_real_pydantic_output_math():
    """Test real CLI with pydantic model output for math operations."""
    adapter = CodexAdapter(model="gpt-5.3-codex-spark")
    result = adapter.run_agent(
        prompt="Calculate 5 + 3 and return result as JSON",
        output_format=MathResult,
    )

    assert isinstance(result, MathResult)
    assert result.result == 8
    assert result.operation.strip()  # Should have some operation description
    assert result.success is True


@pytest.mark.integration
def test_real_pydantic_output_files(temp_stub_dir):
    """Test real CLI with pydantic model output for file listing."""
    adapter = CodexAdapter(
        model="gpt-5.3-codex-spark", profile="test", path=str(temp_stub_dir)
    )
    result = adapter.run_agent(
        prompt=(
            "Run 'ls' to inspect the current directory, identify the Python files "
            "present there, and return them as JSON."
        ),
        output_format=FileListResult,
    )

    assert isinstance(result, FileListResult)
    assert isinstance(result.files, list)
    assert len(result.files) >= 2  # Should find at least our test files
    # Check that path is set (could be full path or relative)
    assert result.path and isinstance(result.path, str)
    # Check that our test files are in the list
    assert any("test_file1.py" in f for f in result.files)
    assert any("test_file2.py" in f for f in result.files)


@pytest.mark.integration
def test_real_simple_model():
    """Test real CLI with simple pydantic model."""
    adapter = CodexAdapter(model="gpt-5.3-codex-spark")
    result = adapter.run_agent(
        prompt="What is the capital of France? Return as JSON",
        output_format=SimpleResult,
    )

    assert isinstance(result, SimpleResult)
    assert isinstance(result.answer, str)
    assert result.answer.strip()
    assert "paris" in result.answer.lower()


@pytest.mark.integration
def test_real_simple_prompt():
    """Test real CLI with simple prompt."""
    adapter = CodexAdapter(model="gpt-5.3-codex-spark")
    result = adapter.run_agent(
        prompt="What is the meaning of life?",
        output_format=SimpleResult,
    )

    assert isinstance(result, SimpleResult)
    assert isinstance(result.answer, str)
    assert result.answer.strip()


def test_real_error_handling():
    """Test real CLI error handling with invalid model."""
    adapter = CodexAdapter(
        model="hello-world-invalid-model"
    )  # Invalid model to trigger error

    # Test with invalid model to trigger error
    with pytest.raises(Exception):  # Could be RuntimeError or other exception types
        adapter.run_agent(
            prompt="Test error handling",
            output_format=MathResult,
        )


@pytest.mark.integration
def test_real_empty_prompt_handling():
    """Test real CLI handling of empty prompt."""
    adapter = CodexAdapter(model="gpt-5.3-codex-spark")

    # Test with empty prompt - should handle gracefully
    result = adapter.run_agent(prompt="")

    # Should return some response (even if it's an error message)
    assert isinstance(result, str)
    assert result.strip()  # Should not be empty


@pytest.mark.integration
def test_real_complex_prompt():
    """Test real CLI with complex prompt and special characters."""
    adapter = CodexAdapter(model="gpt-5.3-codex-spark")
    result = adapter.run_agent(
        prompt="Calculate (2 * 3) + (4 / 2) this using python",
        output_format=MathResult,
    )

    assert isinstance(result, MathResult)
    assert result.result == 8  # (2*3) + (4/2) = 6 + 2 = 8
    assert result.operation.strip()  # Should have some operation description
