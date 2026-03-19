"""Implementation command group."""

import typer

from developer.agents.select_agent_service import SelectAgentService
from developer.orchestrators.implementation_agent import ImplementationAgent
from developer.prompts.builder import OrchestratorPromptBuilder
from developer.quality.services import CheckGateRunner
from developer.tasks.implementation_judge import ImplementationJudge

app = typer.Typer()


@app.command()
def run() -> None:
    """Run the implementation agent."""
    implementation_agent = ImplementationAgent(
        prompt_builder=OrchestratorPromptBuilder(),
        agent_runner=SelectAgentService().select_agent(),
        gate_runner=CheckGateRunner(),
        completion_judge=ImplementationJudge(),
    )
    outcome = implementation_agent.run()

    if outcome.status == "success":
        typer.echo("Implementation run succeeded")
        raise typer.Exit(code=0)

    typer.echo("Implementation run failed")
    raise typer.Exit(code=1)
