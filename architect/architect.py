from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider

load_dotenv()


def create_architect() -> Agent:
    return Agent(
        name="Architect",
        description=(
            "Code specialist orchestrator that analyzes requirements, plans software architecture, "
            "and coordinates code specialists (frontend, backend, code reviewer, QA tester, devops) "
            "for software development projects. Never writes code itself - only plans and delegates."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "What can this code agency do?",
            "Plan and build a REST API with authentication and database integration.",
            "Architect a full-stack web application with frontend and backend components.",
            "Coordinate a code review and QA testing workflow for my pull request.",
            "Design a CI/CD pipeline and deployment strategy for my project.",
        ],
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_architect()).terminal_demo()
