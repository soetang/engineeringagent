import os
from typing import List, Optional, Type

import pytest
from pydantic import BaseModel

from developer.agent_backends.protocol import AgentBackendProtocol
from developer.quality.adapters.agentic_review_adapter import (
    AgenticReviewAdapter,
    AgenticReviewCheck,
    ReviewOutput,
    ReviewStatus,
)
from developer.quality.protocol import CheckStatus


class MockAgent(AgentBackendProtocol):
    """Mock agent for testing without requiring actual CLI adapters."""

    def __init__(
        self,
        profile: Optional[str] = None,
        model: Optional[str] = None,
        path: Optional[str] = None,
    ):
        self.profile = profile
        self.model = model
        self.path = path

    def run_agent(
        self,
        prompt: str,
        output_format: Optional[Type[BaseModel]] = None,
    ) -> BaseModel | str:
        """Return mock review output for agentic review tests."""
        if output_format is None or output_format is str:
            return "Mock response"

        if issubclass(output_format, BaseModel):
            if "def hello_world" in prompt:
                return ReviewOutput(
                    status=ReviewStatus.APPROVED,
                    summary="Code looks good and follows best practices",
                    actions=[],
                )
            if "def test_function_0" in prompt:
                return ReviewOutput(
                    status=ReviewStatus.APPROVED,
                    summary="Test function 0 looks good",
                    actions=[],
                )
            if "def test_function_1" in prompt:
                return ReviewOutput(
                    status=ReviewStatus.FAILED,
                    summary="Test function 1 has issues",
                    actions=["Add proper error handling", "Improve test coverage"],
                )

            return ReviewOutput(
                status=ReviewStatus.NOT_REVIEWABLE,
                summary="Cannot review this type of code",
                actions=["Need more context to review"],
            )

        raise ValueError(f"Unsupported output format: {output_format}")


class MockAgentService:
    """Mock agent service returning mock agents for adapter tests."""

    def __init__(self):
        """Track service selection calls."""
        self.calls = []

    def select_agent(self, backend=None, profile=None, model=None, path=None):
        """Return a mock agent for the provided selection params."""
        self.calls.append(
            {
                "backend": backend,
                "profile": profile,
                "model": model,
                "path": path,
            }
        )
        return MockAgent(profile=profile, model=model, path=path)


def test_agentic_review_adapter_success():
    """Test that the agentic review adapter can run successful reviews."""
    prompt_path = "test_review_prompt.txt"

    try:
        with open(prompt_path, "w") as f:
            f.write(
                """\
Review the following code for quality and provide feedback:

```python
def hello_world():
    return "Hello, World!"
```

Please analyze the code and provide:
- Status: approved, failed, or not_reviewable
- Summary of your findings
- List of recommended actions if any
"""
            )

        adapter = AgenticReviewAdapter(agent_service=MockAgentService())

        checks: List[AgenticReviewCheck] = [
            AgenticReviewCheck(
                check_type="agentic_review",
                prompt_path=prompt_path,
            )
        ]

        results = adapter.run_check(checks)

        assert len(results.results) == 1
        result = results.results[0]

        assert "Agentic Review:" in result.name
        assert result.status in [CheckStatus.PASSED, CheckStatus.FAILED]
        assert "Review Status:" in result.message
        assert "Summary:" in result.message

    finally:
        try:
            os.unlink(prompt_path)
        except:  # noqa: BLE001
            pass


def test_agentic_review_adapter_multiple():
    """Test that the adapter can handle multiple reviews."""
    prompt_paths = []

    try:
        for i in range(2):
            prompt_path = f"test_review_prompt_{i}.txt"
            with open(prompt_path, "w") as f:
                f.write(
                    f"""\
Review the following code for quality and provide feedback:

```python
def test_function_{i}():
    return "Test {i}"
```

Please analyze the code and provide:
- Status: approved, failed, or not_runnable
- Summary of your findings
- List of recommended actions if any
"""
                )
            prompt_paths.append(prompt_path)

        adapter = AgenticReviewAdapter(agent_service=MockAgentService())

        checks: List[AgenticReviewCheck] = [
            AgenticReviewCheck(
                check_type="agentic_review", prompt_path=prompt_paths[0]
            ),
            AgenticReviewCheck(
                check_type="agentic_review", prompt_path=prompt_paths[1]
            ),
        ]

        results = adapter.run_check(checks)

        assert len(results.results) == 2

        for result in results.results:
            assert "Agentic Review:" in result.name
            assert result.status in [CheckStatus.PASSED, CheckStatus.FAILED]
            assert "Review Status:" in result.message
            assert "Summary:" in result.message

    finally:
        for prompt_path in prompt_paths:
            try:
                os.unlink(prompt_path)
            except:  # noqa: BLE001
                pass


def test_agentic_review_adapter_execution_error():
    """Test that missing prompt files raise exceptions."""
    adapter = AgenticReviewAdapter(agent_service=MockAgentService())

    checks: List[AgenticReviewCheck] = [
        AgenticReviewCheck(
            check_type="agentic_review", prompt_path="/nonexistent/path/prompt.txt"
        )
    ]

    with pytest.raises(Exception) as exc_info:
        adapter.run_check(checks)

    assert "Prompt file not found" in str(exc_info.value)


def test_agentic_review_adapter_get_check_type():
    """Test that the adapter returns the correct check type."""
    adapter = AgenticReviewAdapter(agent_service=MockAgentService())

    check_type = adapter.get_check_type()

    assert check_type == AgenticReviewCheck


def test_agentic_review_adapter_backend_selection():
    """Test backend/profile/model/path are forwarded to agent selection."""

    class BackendSelectionMockAgent(AgentBackendProtocol):
        def __init__(
            self,
            name="mock",
            profile: Optional[str] = None,
            model: Optional[str] = None,
            path: Optional[str] = None,
            backend: Optional[str] = None,
        ):
            self.name = name
            self.backend = backend
            self.profile = profile
            self.model = model
            self.path = path
            self.calls = []

        def run_agent(
            self,
            prompt: str,
            output_format: Optional[Type[BaseModel]] = None,
        ) -> BaseModel | str:
            self.calls.append(
                {
                    "prompt": prompt,
                    "output_format": output_format,
                }
            )

            if output_format is None or output_format is str:
                return "mock response"
            if issubclass(output_format, BaseModel):
                return ReviewOutput(
                    status=ReviewStatus.APPROVED,
                    summary="Mock review summary",
                    actions=["Mock action 1", "Mock action 2"],
                )

            raise ValueError(f"Unsupported output format: {output_format}")

    class FakeAgentService:
        def __init__(self):
            self.calls = []

        def select_agent(self, backend=None, profile=None, model=None, path=None):
            self.calls.append(
                {
                    "backend": backend,
                    "profile": profile,
                    "model": model,
                    "path": path,
                }
            )
            return BackendSelectionMockAgent(
                name="selected",
                profile=profile,
                model=model,
                path=path,
                backend=backend,
            )

    prompt_path = "test_backend_prompt.txt"

    try:
        with open(prompt_path, "w") as f:
            f.write(
                """
def hello_world():
    return \"Hello, World!\"
"""
            )

        service = FakeAgentService()
        adapter = AgenticReviewAdapter(agent_service=service)

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

        checks_no_override = [
            AgenticReviewCheck(
                check_type="agentic_review",
                prompt_path=prompt_path,
            )
        ]
        results = adapter.run_check(checks_no_override)
        assert len(results.results) == 1
        assert results.results[0].status == CheckStatus.PASSED
        assert len(service.calls) == 1
        assert service.calls[0]["backend"] is None
        assert service.calls[0]["profile"] is None
        assert service.calls[0]["model"] is None
        assert service.calls[0]["path"] is None

        service.calls.clear()
        check_with_path = AgenticReviewCheck(
            check_type="agentic_review",
            prompt_path=prompt_path,
            path="/tmp",
            backend="vibe",
            profile="testagent",
        )
        results = adapter.run_check([check_with_path])
        assert len(results.results) == 1
        assert results.results[0].status == CheckStatus.PASSED
        assert len(service.calls) == 1
        assert service.calls[0]["backend"] == "vibe"
        assert service.calls[0]["profile"] == "testagent"
        assert service.calls[0]["model"] is None
        assert service.calls[0]["path"] == "/tmp"

        service.calls.clear()
        check_vibe = AgenticReviewCheck(
            check_type="agentic_review", prompt_path=prompt_path, backend="vibe"
        )
        results = adapter.run_check([check_vibe])
        assert len(results.results) == 1
        assert len(service.calls) == 1
        assert service.calls[0]["backend"] == "vibe"

        class FailingAgentService:
            def select_agent(self, backend=None, profile=None, model=None, path=None):
                if backend == "vibe" and model is not None:
                    raise ValueError(
                        "Vibe backend does not support `model`; use `profile` to select a Vibe agent."
                    )
                raise ValueError(f"Unknown backend: {backend}")

        adapter = AgenticReviewAdapter(agent_service=FailingAgentService())
        check_unknown = AgenticReviewCheck(
            check_type="agentic_review",
            prompt_path=prompt_path,
            backend="unknown_backend",
        )
        with pytest.raises(Exception) as exc_info:
            adapter.run_check([check_unknown])
        assert "Error executing agentic review" in str(exc_info.value)
        assert "Unknown backend: unknown_backend" in str(exc_info.value)

        adapter = AgenticReviewAdapter(agent_service=FailingAgentService())
        check_vibe_model = AgenticReviewCheck(
            check_type="agentic_review",
            prompt_path=prompt_path,
            backend="vibe",
            model="devstral-small",
        )
        with pytest.raises(Exception) as exc_info:
            adapter.run_check([check_vibe_model])
        assert "Error executing agentic review" in str(exc_info.value)
        assert "Vibe backend does not support `model`" in str(exc_info.value)

    finally:
        try:
            os.unlink(prompt_path)
        except:  # noqa: BLE001
            pass


def test_agentic_review_adapter_backend_field():
    """Test that AgenticReviewCheck accepts backend/profile/model fields."""
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


def test_agentic_review_adapter_appends_strict_json_contract():
    """Test that review prompts include an explicit JSON-only response contract."""

    class PromptCapturingAgent(AgentBackendProtocol):
        def __init__(self):
            self.prompts: list[str] = []

        def run_agent(
            self,
            prompt: str,
            output_format: Optional[Type[BaseModel]] = None,
        ) -> BaseModel | str:
            self.prompts.append(prompt)
            return ReviewOutput(
                status=ReviewStatus.APPROVED,
                summary="Prompt captured",
                actions=[],
            )

    class PromptCapturingAgentService:
        def __init__(self):
            self.agent = PromptCapturingAgent()

        def select_agent(self, backend=None, profile=None, model=None, path=None):
            return self.agent

    prompt_path = "test_prompt_contract.txt"

    try:
        with open(prompt_path, "w") as f:
            f.write("Review this code change.")

        service = PromptCapturingAgentService()
        adapter = AgenticReviewAdapter(agent_service=service)
        adapter.run_check([AgenticReviewCheck(prompt_path=prompt_path)])

        assert len(service.agent.prompts) == 1
        prompt = service.agent.prompts[0]
        assert "Return a single JSON object only." in prompt
        assert '"status": "approved" | "failed" | "not_reviewable"' in prompt
        assert 'return an empty array for "actions"' in prompt
    finally:
        try:
            os.unlink(prompt_path)
        except:  # noqa: BLE001
            pass
