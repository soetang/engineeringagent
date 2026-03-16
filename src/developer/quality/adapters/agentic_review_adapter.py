from typing import List, Optional
from pydantic import BaseModel, Field
from enum import Enum
from ..protocol import CheckAdapter, CheckResult, CheckResultList, CheckStatus
from ..models import CheckType
from developer.agents.protocol import AgentProtocol
from developer.agents.adapters.codex_adapter import CodexAdapter


class ReviewStatus(str, Enum):
    """Enum representing the status of a code review."""

    APPROVED = "approved"
    FAILED = "failed"
    NOT_REVIEWABLE = "not_reviewable"


class ReviewOutput(BaseModel):
    """Represents the output format for agentic code reviews."""

    status: ReviewStatus = Field(
        ..., description="Status of the review: approved, failed, or not_reviewable"
    )
    summary: str = Field(..., description="Summary of the review findings")
    actions: List[str] = Field(
        default_factory=list, description="List of recommended actions or fixes"
    )

    @classmethod
    def model_json_schema(cls, **kwargs) -> dict:  # type: ignore[override]
        """Generate JSON schema without descriptions in enum references."""
        schema = super().model_json_schema(**kwargs)

        # Remove descriptions from enum properties to avoid $ref issues
        if "properties" in schema and "status" in schema["properties"]:
            status_schema = schema["properties"]["status"]
            if "description" in status_schema:
                del status_schema["description"]

        return schema


class AgenticReviewCheck(CheckType):
    """Represents an agentic code review check."""

    prompt_path: str = Field(
        ..., description="Path to the prompt file for the code review"
    )
    model: Optional[str] = Field(
        default=None, description="Optional model to use for the review"
    )
    profile: Optional[str] = Field(
        default=None, description="Optional profile to use for the review"
    )
    backend: Optional[str] = Field(
        default=None, description="Optional backend to use for the review"
    )
    path: Optional[str] = Field(
        default=None, description="Optional working directory path for the review"
    )

    def __init__(self, **data):
        # Set default check_type to "agentic_review" if not provided
        if "check_type" not in data:
            data["check_type"] = "agentic_review"
        super().__init__(**data)


class AgenticReviewAdapter(CheckAdapter):
    """Adapter for running agentic code reviews as quality checks."""

    def __init__(
        self, agent: Optional[AgentProtocol] = None, backend: Optional[str] = None
    ):
        """Initialize the adapter with an optional agent protocol and backend."""
        if agent:
            self.agent = agent
        else:
            self.agent = self._get_agent_for_backend(backend)

    def _get_agent_for_backend(self, backend: Optional[str] = None) -> AgentProtocol:
        """Factory function to get agent implementation for backend."""
        if backend is None or backend == "codex":
            return CodexAdapter()
        # Add more backends here as needed
        # elif backend == "other_backend":
        #     return OtherAgentAdapter()
        else:
            raise ValueError(f"Unknown backend: {backend}")

    def run_check(self, checks: List[AgenticReviewCheck]) -> CheckResultList:
        """Run the agentic review checks and return the results."""
        results = []

        for check in checks:
            try:
                # Get the appropriate agent for this backend
                agent_for_check = (
                    self._get_agent_for_backend(check.backend) if check.backend else self.agent
                )

                # Read and execute the prompt
                with open(check.prompt_path, "r") as f:
                    prompt = f.read()

                # Run the agent with the prompt and expected output format
                review_output = agent_for_check.run_agent(
                    prompt=prompt,
                    output_format=ReviewOutput,  # type: ignore[arg-type]
                    model=check.model,
                    profile=check.profile,
                    path=check.path,
                )

                # Map review status to check status using explicit mapping
                status_map = {
                    ReviewStatus.APPROVED: CheckStatus.PASSED,
                    ReviewStatus.FAILED: CheckStatus.FAILED,
                }
                status = status_map.get(review_output.status)
                
                if status is None:  # NOT_RUNABLE case
                    # Raise an error for not_reviewable status
                    raise Exception(
                        f"Agentic review is not reviewable for prompt: {check.prompt_path}. "
                        f"Reason: {review_output.summary}"
                    )

                # Create summary message
                message = f"Review Status: {review_output.status.value}\n"
                message += f"Summary: {review_output.summary}\n"
                if review_output.actions:
                    message += "Actions:\n" + "\n".join(
                        f"- {action}" for action in review_output.actions
                    )

                results.append(
                    CheckResult(
                        name=f"Agentic Review: {check.prompt_path}",
                        status=status,
                        message=message,
                    )
                )

            except FileNotFoundError as e:
                # Prompt file not found
                raise Exception(
                    f"Prompt file not found: {check.prompt_path} - {str(e)}"
                )
            except Exception as e:
                # Other execution errors
                raise Exception(
                    f"Error executing agentic review: {check.prompt_path} - {str(e)}"
                )

        return CheckResultList(results=results)

    def get_check_type(self) -> type[BaseModel]:
        """Return the pydantic model representing the check type."""
        return AgenticReviewCheck
