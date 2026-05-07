from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning
from dotenv import load_dotenv

from config import get_default_model, is_openai_provider

load_dotenv()


def create_qa_tester() -> Agent:
    return Agent(
        name="QA Tester",
        description=(
            "Testing and quality assurance specialist that writes unit tests, integration tests, "
            "and E2E tests using frameworks like Jest, Pytest, JUnit, Cypress, and Playwright. "
            "Analyzes test coverage, identifies bugs, discovers edge cases, plans test strategies, "
            "and ensures software quality through comprehensive testing."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Write unit tests for my Python module using Pytest.",
            "Create E2E tests for my web application using Playwright.",
            "Analyze test coverage and identify gaps in my codebase.",
            "Identify edge cases and potential bugs in this function.",
            "Plan a comprehensive test strategy for my project.",
        ],
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_qa_tester()).terminal_demo()
