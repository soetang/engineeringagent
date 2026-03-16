import tempfile
import os
from typing import List, Optional, Type, Union
from pydantic import BaseModel
import pytest
from developer.quality.adapters import AgenticReviewAdapter, AgenticReviewCheck
from developer.quality.protocol import CheckStatus
from developer.agents.protocol import AgentProtocol


class MockAgent(AgentProtocol):
    """Mock agent for testing without requiring actual Codex CLI."""

    def run_agent(
        self,
        prompt: str,
        output_format: Type[BaseModel] = str,  # type: ignore[type-arg]
        model: Optional[str] = None,
        profile: Optional[str] = None,
        path: Optional[str] = None,
    ) -> Union[BaseModel, str]:
        """Mock agent that returns predefined responses."""
        if output_format == str or output_format is str:
            return "Mock response"

        elif issubclass(output_format, BaseModel):
            # Return a mock review output
            from developer.quality.adapters.agentic_review_adapter import (
                ReviewOutput,
                ReviewStatus,
            )

            # Simple logic: if prompt contains "def hello_world", approve it
            if "def hello_world" in prompt:
                return ReviewOutput(
                    status=ReviewStatus.APPROVED,
                    summary="Code looks good and follows best practices",
                    actions=[],
                )
            elif "def test_function_0" in prompt:
                return ReviewOutput(
                    status=ReviewStatus.APPROVED,
                    summary="Test function 0 looks good",
                    actions=[],
                )
            elif "def test_function_1" in prompt:
                return ReviewOutput(
                    status=ReviewStatus.FAILED,
                    summary="Test function 1 has issues",
                    actions=["Add proper error handling", "Improve test coverage"],
                )
            else:
                return ReviewOutput(
                    status=ReviewStatus.NOT_REVIEWABLE,
                    summary="Cannot review this type of code",
                    actions=["Provide more context", "Specify review criteria"],
                )

        else:
            raise ValueError(f"Unsupported output format: {output_format}")


def test_agentic_review_adapter_with_mock():
    """Test the agentic review adapter using mock agent."""
    # Create a temporary prompt file
    prompt_path = "test_mock_prompt.txt"

    try:
        with open(prompt_path, "w") as f:
            f.write("""
Review the following code for quality and provide feedback:

```python
def hello_world():
    return "Hello, World!"
```

Please analyze the code and provide:
- Status: approved, failed, or not_runnable
- Summary of your findings
- List of recommended actions if any
""")

        # Create the adapter with mock agent
        adapter = AgenticReviewAdapter(agent=MockAgent())

        # Create a review check
        checks: List[BaseModel] = [
            AgenticReviewCheck(
                check_type="agentic_review", prompt_path=prompt_path, path="."
            )
        ]

        # Run the check
        results = adapter.run_check(checks)

        # Verify results
        assert len(results.results) == 1
        result = results.results[0]

        assert "Agentic Review:" in result.name
        assert result.status == CheckStatus.PASSED  # Should be approved
        assert "Review Status: approved" in result.message
        assert "Summary: Code looks good and follows best practices" in result.message

    finally:
        # Clean up
        try:
            os.unlink(prompt_path)
        except:
            pass


def test_agentic_review_adapter_multiple_with_mock():
    """Test the agentic review adapter with multiple checks using mock agent."""
    # Create multiple prompt files
    prompt_paths = []

    try:
        for i in range(2):
            prompt_path = f"test_mock_prompt_{i}.txt"
            with open(prompt_path, "w") as f:
                f.write(f"""
Review the following code for quality and provide feedback:

```python
def test_function_{i}():
    return "Test {i}"
```

Please analyze the code and provide:
- Status: approved, failed, or not_runnable
- Summary of your findings
- List of recommended actions if any
""")
            prompt_paths.append(prompt_path)

        # Create the adapter with mock agent
        adapter = AgenticReviewAdapter(agent=MockAgent())

        # Create multiple review checks
        checks: List[BaseModel] = [
            AgenticReviewCheck(
                check_type="agentic_review", prompt_path=prompt_paths[0], path="."
            ),
            AgenticReviewCheck(
                check_type="agentic_review", prompt_path=prompt_paths[1], path="."
            ),
        ]

        # Run the checks
        results = adapter.run_check(checks)

        # Verify we got results for both checks
        assert len(results.results) == 2

        # Check first result (should be approved)
        result0 = results.results[0]
        assert "Agentic Review:" in result0.name
        assert result0.status == CheckStatus.PASSED
        assert "Review Status: approved" in result0.message
        assert "Test function 0 looks good" in result0.message

        # Check second result (should be failed)
        result1 = results.results[1]
        assert "Agentic Review:" in result1.name
        assert result1.status == CheckStatus.FAILED
        assert "Review Status: failed" in result1.message
        assert "Test function 1 has issues" in result1.message
        assert "Add proper error handling" in result1.message
        assert "Improve test coverage" in result1.message

    finally:
        # Clean up
        for prompt_path in prompt_paths:
            try:
                os.unlink(prompt_path)
            except:
                pass


def test_agentic_review_adapter_not_reviewable_with_mock():
    """Test the agentic review adapter with not_reviewable status using mock agent."""
    # Create a prompt file with unknown code
    prompt_path = "test_not_runnable_prompt.txt"

    try:
        with open(prompt_path, "w") as f:
            f.write("""
Review the following unknown code:

```some_unknown_language
unknown code here
```

Please analyze the code and provide feedback.
- Status: approved, failed, or not_reviewable
""")

        # Create the adapter with mock agent
        adapter = AgenticReviewAdapter(agent=MockAgent())

        # Create a review check
        checks: List[BaseModel] = [
            AgenticReviewCheck(
                check_type="agentic_review", prompt_path=prompt_path, path="."
            )
        ]

        # Run the check and expect an exception for not_runnable status
        with pytest.raises(Exception) as exc_info:
            adapter.run_check(checks)

        # Verify the exception message
        assert "Agentic review is not reviewable" in str(exc_info.value)
        assert "Cannot review this type of code" in str(exc_info.value)

    finally:
        # Clean up
        try:
            os.unlink(prompt_path)
        except:
            pass
