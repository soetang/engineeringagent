import pytest
from pydantic import BaseModel

from developer.agent_backends.adapters.vibe_adapter import VibeAdapter
from developer.quality.adapters.agentic_review_adapter import ReviewOutput, ReviewStatus


class VibeTestModel(BaseModel):
    """Test model for Vibe adapter testing."""

    name: str
    value: int
    items: list[str]


@pytest.fixture
def vibe_adapter() -> VibeAdapter:
    """Fixture providing VibeAdapter instance for tests."""
    return VibeAdapter(profile="testagent")


def test_vibe_adapter_uses_profile_for_agent_flag():
    """Vibe command building should use profile for the agent selector."""
    adapter = VibeAdapter(profile="testagent", path="/tmp/workspace")

    command = adapter._build_vibe_command("hello")

    assert command == [
        "vibe",
        "-p",
        "hello",
        "--output",
        "json",
        "--agent",
        "testagent",
        "--workdir",
        "/tmp/workspace",
    ]


def test_vibe_adapter_rejects_model_configuration():
    """Vibe adapters should reject unsupported raw model configuration."""
    with pytest.raises(
        ValueError,
        match="Vibe backend does not support `model`; use `profile`",
    ):
        VibeAdapter(model="devstral-small")


@pytest.mark.integration
class TestVibeAdapter:
    """Test suite for Vibe CLI adapter - integration tests requiring Vibe CLI."""

    def test_string_output(self, vibe_adapter):
        """Test basic string output from Vibe adapter."""
        result = vibe_adapter.run_agent("What is your name?")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_structured_output_review(self, vibe_adapter):
        """Test structured output with ReviewOutput model."""
        review = vibe_adapter.run_agent(
            "Provide a code review for this empty prompt", output_format=ReviewOutput
        )

        assert isinstance(review, ReviewOutput)
        assert review.status in [
            ReviewStatus.APPROVED,
            ReviewStatus.FAILED,
            ReviewStatus.NOT_REVIEWABLE,
        ]
        assert isinstance(review.summary, str)
        assert len(review.summary) > 0

    def test_structured_output_custom_model(self, vibe_adapter):
        """Test structured output with custom Pydantic model."""
        test_data = vibe_adapter.run_agent(
            "Return name='test', value=42, items=['a', 'b']",
            output_format=VibeTestModel,
        )

        assert isinstance(test_data, VibeTestModel)
        assert test_data.name == "test"
        assert test_data.value == 42
        assert test_data.items == ["a", "b"]

    def test_path_parameter(self, tmp_path, vibe_adapter):
        """Test working directory parameter."""
        test_file = tmp_path / "test.txt"
        test_file.write_text("Hello from temp directory!")

        adapter = VibeAdapter(profile="testagent", path=str(tmp_path))
        result = adapter.run_agent("What is in test.txt?")

        assert isinstance(result, str)
        assert "Hello from temp directory" in result

    def test_error_handling(self, vibe_adapter):
        """Test error handling for invalid prompts."""
        # This should not raise an exception, but return a meaningful response
        result = vibe_adapter.run_agent("This is a valid prompt")

        assert isinstance(result, str)
        assert len(result) > 0

    def test_schema_compliance(self, vibe_adapter):
        """Test that Vibe adapter respects schema requirements."""

        # Test with a model that has required fields
        class StrictModel(BaseModel):
            required_field: str
            optional_field: str = "default"

        result = vibe_adapter.run_agent(
            "Return required_field='test_value'", output_format=StrictModel
        )

        assert isinstance(result, StrictModel)
        assert hasattr(result, "required_field")
        assert hasattr(result, "optional_field")
