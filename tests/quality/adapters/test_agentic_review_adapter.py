import tempfile
import os
import shutil
from typing import List, Optional, Type, Union
from pydantic import BaseModel
import pytest
from developer.agents.protocol import AgentProtocol
from developer.quality.adapters import AgenticReviewAdapter, AgenticReviewCheck
from developer.quality.protocol import CheckStatus


class MockAgent(AgentProtocol):
    """Mock agent for testing without requiring actual Codex CLI."""

    def __init__(self, profile: Optional[str] = None, model: Optional[str] = None):
        """Initialize mock agent."""
        self.profile = profile
        self.model = model

    def run_agent(
        self,
        prompt: str,
        output_format: Type[BaseModel] = str,  # type: ignore[type-arg]
        model: Optional[str] = None,
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

            # Simple logic: if prompt contains known functions, approve them
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
                    actions=["Need more context to review"],
                )


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

        # Create the adapter with mock agent
        adapter = AgenticReviewAdapter(agent=MockAgent())

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
    adapter = AgenticReviewAdapter(agent=MockAgent())

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
    adapter = AgenticReviewAdapter(agent=MockAgent())

    check_type = adapter.get_check_type()

    assert check_type == AgenticReviewCheck


def test_agentic_review_adapter_backend_selection():
    """Test that the adapter correctly handles backend parameter using mock agent."""
    from typing import Optional
    from typing import Optional
    from developer.agents.protocol import AgentProtocol
    from developer.agents.adapters.codex_adapter import CodexAdapter
    from developer.agents.adapters.vibe_adapter import VibeAdapter
    from developer.quality.adapters.agentic_review_adapter import (
        ReviewOutput,
        ReviewStatus,
    )

    # Create a mock agent that doesn't require actual API calls
    class MockAgent(AgentProtocol):
        def __init__(self, name="mock"):
            self.name = name
            self.calls = []

        def run_agent(
            self,
            prompt: str,
            output_format: type = str,
            model: Optional[str] = None,
            profile: Optional[str] = None,
            path: Optional[str] = None,
        ):
            self.calls.append(
                {
                    "prompt": prompt,
                    "output_format": output_format,
                    "model": model,
                    "profile": profile,
                    "path": path,
                }
            )

            # Return a mock review output
            if output_format == str:
                return "mock response"
            else:
                return ReviewOutput(
                    status=ReviewStatus.APPROVED,
                    summary="Mock review summary",
                    actions=["Mock action 1", "Mock action 2"],
                )

    # Create a temporary prompt file
    prompt_path = "test_backend_prompt.txt"

    try:
        with open(prompt_path, "w") as f:
            f.write("Test prompt content")

        # Test 1: Default backend (should use CodexAdapter by default)
        adapter_default = AgenticReviewAdapter()
        assert isinstance(adapter_default.agent, CodexAdapter)

        # Test 2: Explicit backend selection in adapter constructor
        mock_agent = MockAgent("test_backend")
        adapter_with_backend = AgenticReviewAdapter(agent=mock_agent)
        assert adapter_with_backend.agent == mock_agent

        # Test 3: Test backend field extraction from AgenticReviewCheck
        check = AgenticReviewCheck(
            check_type="agentic_review",
            prompt_path=prompt_path,
            backend="codex",
            profile="test_profile",
            model="test_model",
        )
        assert check.backend == "codex"
        assert check.profile == "test_profile"
        assert check.model == "test_model"

        # Test 4: Test backend field extraction from raw dict
        raw_check = {
            "check_type": "agentic_review",
            "prompt_path": prompt_path,
            "backend": "codex",
            "profile": "test_profile",
            "model": "test_model",
        }
        assert raw_check.get("backend") == "codex"
        assert raw_check.get("profile") == "test_profile"
        assert raw_check.get("model") == "test_model"

        # Test 5: Test _get_agent_for_check method with new SelectAgentService
        adapter = AgenticReviewAdapter()

        # Test agent selection through the new service
        check_none = AgenticReviewCheck(
            check_type="agentic_review", prompt_path=prompt_path
        )
        agent_none = adapter._get_agent_for_check(check_none)
        assert isinstance(agent_none, CodexAdapter)  # Should use default from config

        check_vibe = AgenticReviewCheck(
            check_type="agentic_review", prompt_path=prompt_path, backend="vibe"
        )
        agent_vibe = adapter._get_agent_for_check(check_vibe)
        assert isinstance(agent_vibe, VibeAdapter)

        # Should raise ValueError for unknown backend
        check_unknown = AgenticReviewCheck(
            check_type="agentic_review",
            prompt_path=prompt_path,
            backend="unknown_backend",
        )
        with pytest.raises(ValueError) as exc_info:
            adapter._get_agent_for_check(check_unknown)
        assert "Unknown backend: unknown_backend" in str(exc_info.value)

    finally:
        # Clean up
        try:
            os.unlink(prompt_path)
        except:
            pass


def test_agentic_review_adapter_backend_field():
    """Test that AgenticReviewCheck model accepts backend field."""
    check = AgenticReviewCheck(
        check_type="agentic_review",
        prompt_path="dummy.txt",
        backend="test_backend",
        profile="test_profile",
        model="test_model",
    )

    assert check.backend == "test_backend"
    assert check.profile == "test_profile"
    assert check.model == "test_model"
