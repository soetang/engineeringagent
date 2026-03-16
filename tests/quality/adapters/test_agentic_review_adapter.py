import tempfile
import os
import shutil
from typing import List
from pydantic import BaseModel
import pytest
from developer.quality.adapters import AgenticReviewAdapter, AgenticReviewCheck
from developer.quality.protocol import CheckStatus


def test_agentic_review_adapter_success():
    """Test that the agentic review adapter can run successful reviews."""
    # Create a temporary prompt file in current directory (must be git repo for codex)
    prompt_path = "test_review_prompt.txt"

    try:
        with open(prompt_path, "w") as f:
            f.write("""
Review the following code for quality and provide feedback:

```python
def hello_world():
    return "Hello, World!"
```

Please analyze the code and provide:
- Status: approved, failed, or not_reviewable
- Summary of your findings
- List of recommended actions if any
""")

        # Create the adapter
        adapter = AgenticReviewAdapter()

        # Create a review check
        checks: List[BaseModel] = [
            AgenticReviewCheck(
                check_type="agentic_review",
                prompt_path=prompt_path,
                path=".",  # Use current directory
            )
        ]

        # Run the check
        results = adapter.run_check(checks)

        # Verify results
        assert len(results.results) == 1
        result = results.results[0]

        assert "Agentic Review:" in result.name
        assert result.status in [CheckStatus.PASSED, CheckStatus.FAILED]
        assert "Review Status:" in result.message
        assert "Summary:" in result.message

    finally:
        # Clean up
        try:
            os.unlink(prompt_path)
        except:
            pass


def test_agentic_review_adapter_multiple():
    """Test that the agentic review adapter can handle multiple reviews."""
    # Create multiple prompt files in current directory
    prompt_paths = []

    try:
        for i in range(2):
            prompt_path = f"test_review_prompt_{i}.txt"
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

        # Create the adapter
        adapter = AgenticReviewAdapter()

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

        for result in results.results:
            assert "Agentic Review:" in result.name
            assert result.status in [CheckStatus.PASSED, CheckStatus.FAILED]
            assert "Review Status:" in result.message
            assert "Summary:" in result.message

    finally:
        # Clean up
        for prompt_path in prompt_paths:
            try:
                os.unlink(prompt_path)
            except:
                pass


def test_agentic_review_adapter_execution_error():
    """Test that the agentic review adapter raises exceptions for execution errors."""
    # Create the adapter
    adapter = AgenticReviewAdapter()

    # Test with non-existent prompt file
    checks: List[BaseModel] = [
        AgenticReviewCheck(
            check_type="agentic_review", prompt_path="/nonexistent/path/prompt.txt"
        )
    ]

    with pytest.raises(Exception) as exc_info:
        adapter.run_check(checks)

    assert "Prompt file not found" in str(exc_info.value)


def test_agentic_review_adapter_get_check_type():
    """Test that the adapter returns the correct check type."""
    adapter = AgenticReviewAdapter()

    check_type = adapter.get_check_type()

    assert check_type == AgenticReviewCheck
