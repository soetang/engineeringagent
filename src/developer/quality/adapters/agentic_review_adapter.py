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

    def __init__(self, agent: Optional[AgentProtocol] = None):
        """Initialize the adapter with an optional agent protocol."""
        self.agent = agent or CodexAdapter()

    def run_check(self, checks: List[BaseModel]) -> CheckResultList:
        """Run the agentic review checks and return the results."""
        results = []

        for check in checks:
            # Accept both AgenticReviewCheck from adapter and raw dicts
            if isinstance(check, AgenticReviewCheck):
                review_check = check
            elif (
                isinstance(check, dict)
                and check.get("check_type") == "agentic_review"
                and "prompt_path" in check
            ):
                # Handle raw dict review checks
                review_check = check
            else:
                continue

            try:
                # Extract prompt path and optional parameters from the check
                if isinstance(review_check, AgenticReviewCheck):
                    prompt_path = review_check.prompt_path
                    model = review_check.model
                    profile = review_check.profile
                    path = review_check.path
                else:
                    # Handle raw dict check
                    prompt_path = review_check["prompt_path"]
                    model = review_check.get("model")
                    profile = review_check.get("profile")
                    path = review_check.get("path")

                # Validate that we have a prompt path
                if not prompt_path:
                    raise ValueError("prompt_path is required for agentic review checks")

                # Read and execute the prompt
                with open(prompt_path, "r") as f:
                    prompt = f.read()

                # Run the agent with the prompt and expected output format
                review_output = self.agent.run_agent(
                    prompt=prompt,
                    output_format=ReviewOutput,  # type: ignore[arg-type]
                    model=model,
                    profile=profile,
                    path=path,
                )

                # Map review status to check status
                if review_output.status == ReviewStatus.APPROVED:
                    status = CheckStatus.PASSED
                elif review_output.status == ReviewStatus.FAILED:
                    status = CheckStatus.FAILED
                else:  # NOT_RUNABLE
                    # Raise an error for not_reviewable status
                    raise Exception(
                        f"Agentic review is not reviewable for prompt: {prompt_path}. "
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
                        name=f"Agentic Review: {prompt_path}",
                        status=status,
                        message=message,
                    )
                )

            except FileNotFoundError as e:
                # Prompt file not found
                raise Exception(f"Prompt file not found: {prompt_path} - {str(e)}")  # pyrefly: ignore[unbound-name]
            except Exception as e:
                # Other execution errors
                raise Exception(
                    f"Error executing agentic review: {prompt_path} - {str(e)}"  # pyrefly: ignore[unbound-name]
                )

        return CheckResultList(results=results)

    def get_check_type(self) -> type[BaseModel]:
        """Return the pydantic model representing the check type."""
        return AgenticReviewCheck
