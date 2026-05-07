from agency_swarm import Agent, ModelSettings
from openai.types.shared import Reasoning

from config import get_default_model, is_openai_provider


def create_frontend_dev() -> Agent:
    return Agent(
        name="Frontend Dev",
        description=(
            "Frontend development specialist skilled in React, Vue, Angular, and Svelte frameworks. "
            "Implements responsive UI components, manages state, writes TypeScript/JavaScript, "
            "and ensures accessibility and optimal user experience."
        ),
        instructions="./instructions.md",
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(effort="medium", summary="auto") if is_openai_provider() else None,
        ),
        conversation_starters=[
            "Build a responsive dashboard layout with React and Tailwind CSS.",
            "Create a reusable form component with validation in TypeScript.",
            "Implement a data table with sorting, filtering, and pagination.",
            "Set up state management with Redux Toolkit for a shopping cart.",
        ],
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_frontend_dev()).terminal_demo()
