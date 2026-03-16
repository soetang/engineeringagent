from pathlib import Path

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


@pytest.mark.integration
class TestRealIntegration:
    """Real integration tests using actual Codex CLI."""

    def test_real_string_output(self):
        """Test real CLI string output."""
        adapter = CodexAdapter()
        result = adapter.run_agent(
            prompt="What is 2 + 2?",
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        # Since the model is not deterministic, we just check that we get a string response.
        assert isinstance(result, str)

    def test_real_pydantic_output_math(self):
        """Test real CLI with pydantic model output for math operations."""
        adapter = CodexAdapter()
        result = adapter.run_agent(
            prompt="Calculate 5 + 3 and return result as JSON",
            output_format=MathResult,
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        assert isinstance(result, MathResult)
        assert result.result == 8
        assert result.operation.strip()  # Should have some operation description
        assert result.success is True

    def test_real_pydantic_output_files(self):
        """Test real CLI with pydantic model output for file listing."""
        # Use stub directory for testing
        stub_dir = str(Path(__file__).parent / "stub_data")

        adapter = CodexAdapter()
        result = adapter.run_agent(
            prompt="List Python files in current directory as JSON",
            output_format=FileListResult,
            path=stub_dir,  # Use path parameter instead of changing directory
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        assert isinstance(result, FileListResult)
        assert isinstance(result.files, list)
        assert len(result.files) >= 2  # Should find at least our test files
        # Check that path is set (could be full path or relative)
        assert result.path and isinstance(result.path, str)
        # Check that our test files are in the list
        assert any("test_file1.py" in f for f in result.files)
        assert any("test_file2.py" in f for f in result.files)

    def test_real_simple_model(self):
        """Test real CLI with simple pydantic model."""
        adapter = CodexAdapter()
        result = adapter.run_agent(
            prompt="What is the capital of France? Return as JSON",
            output_format=SimpleResult,
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        assert isinstance(result, SimpleResult)
        assert isinstance(result.answer, str)
        assert result.answer.strip()
        assert "paris" in result.answer.lower()

    def test_real_simple_prompt(self):
        """Test real CLI with simple prompt."""
        adapter = CodexAdapter()
        result = adapter.run_agent(
            prompt="What is the meaning of life?",
            output_format=SimpleResult,
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        assert isinstance(result, SimpleResult)
        assert isinstance(result.answer, str)
        assert result.answer.strip()

    def test_real_error_handling(self):
        """Test real CLI error handling with invalid model."""
        adapter = CodexAdapter()

        # Test with invalid model to trigger error
        with pytest.raises(Exception):  # Could be RuntimeError or other exception types
            adapter.run_agent(
                prompt="Test error handling",
                output_format=MathResult,
                model="invalid-model-name-that-does-not-exist",
            )

    def test_real_empty_prompt_handling(self):
        """Test real CLI handling of empty prompt."""
        adapter = CodexAdapter()

        # Test with empty prompt - should handle gracefully
        result = adapter.run_agent(prompt="")

        # Should return some response (even if it's an error message)
        assert isinstance(result, str)
        assert result.strip()  # Should not be empty

    def test_real_complex_prompt(self):
        """Test real CLI with complex prompt and special characters."""
        adapter = CodexAdapter()
        result = adapter.run_agent(
            prompt="Calculate (2 * 3) + (4 / 2) and explain the steps. Return result as JSON.",
            output_format=MathResult,
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        assert isinstance(result, MathResult)
        assert result.result == 8  # (2*3) + (4/2) = 6 + 2 = 8
        assert result.operation.strip()  # Should have some operation description


@pytest.mark.slow
@pytest.mark.integration
class TestSlowIntegration:
    """Slow integration tests that may take longer to execute."""

    def test_large_response_handling(self):
        """Test handling of large responses."""
        adapter = CodexAdapter()
        result = adapter.run_agent(
            prompt="Generate a list of 10 programming languages with their creators as JSON",
            output_format=SimpleResult,
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        assert isinstance(result, SimpleResult)
        assert len(result.answer) > 100  # Should be a reasonably long response

    def test_multiple_sequential_calls(self):
        """Test multiple sequential calls to ensure no state issues."""
        adapter = CodexAdapter()

        # First call
        result1 = adapter.run_agent(
            prompt="What is 1 + 1?",
            output_format=MathResult,
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        # Second call
        result2 = adapter.run_agent(
            prompt="What is 2 + 2?",
            output_format=MathResult,
            model="gpt-5.1-codex-mini",
        )

        # Third call
        result3 = adapter.run_agent(
            prompt="What is 3 + 3?",
            output_format=MathResult,
            model="gpt-5.1-codex-mini",
        )

        # Check that results are reasonable (exact values may vary based on CLI response)
        assert result1.result in [2, 1 + 1]  # Could be literal 2 or expression result
        assert result2.result in [4, 2 + 2]
        assert result3.result in [6, 3 + 3]
        assert all(r.operation.strip() for r in [result1, result2, result3])
        assert all(r.success is True for r in [result1, result2, result3])

    def test_real_path_parameter(self):
        """Test the path parameter functionality."""
        # Test with stub directory
        stub_dir = str(Path(__file__).parent / "stub_data")

        adapter = CodexAdapter()
        result = adapter.run_agent(
            prompt="List files in the specified directory",
            output_format=FileListResult,
            path=stub_dir,
            model="gpt-5.1-codex-mini",  # Use fast model
        )

        assert isinstance(result, FileListResult)
        assert isinstance(result.files, list)
        assert len(result.files) >= 2
        # Path should reflect the stub directory
        assert stub_dir in result.path or result.path == stub_dir
