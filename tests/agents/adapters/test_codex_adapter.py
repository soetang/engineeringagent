"""Real integration tests for Codex CLI adapter."""

import subprocess
from pathlib import Path
from shutil import copytree

import pytest
from pydantic import BaseModel

from developer.agents.adapters.codex_adapter import CodexAdapter


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
