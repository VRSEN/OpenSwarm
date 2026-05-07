from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider

load_dotenv()


def create_code_reviewer() -> Agent:
    return Agent(
        name="CodeReviewer",
        description=(
            "Code review specialist that analyzes code for quality, security vulnerabilities, "
            "performance issues, and adherence to best practices. Provides actionable feedback "
            "on SOLID principles, DRY, KISS, code smells, and refactoring opportunities."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Review this code for quality and best practices.",
            "Check this function for security vulnerabilities.",
            "Identify performance issues in my code.",
            "What code smells do you see and how should I refactor?",
            "Does this code follow SOLID principles?",
        ],
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_code_reviewer()).terminal_demo()
