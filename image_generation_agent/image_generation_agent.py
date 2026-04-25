from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import LoadFileAttachment
from openai.types.shared.reasoning import Reasoning
from shared_tools import CopyFile

from config import get_default_model, is_openai_provider


def create_image_generation_agent() -> Agent:
    return Agent(
        name="Image Agent",
        description="A specialized agent for image generation, editing, and composition.",
        instructions="instructions.md",
        tools_folder="./tools",
        tools=[LoadFileAttachment, CopyFile],
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(summary="auto", effort="medium") if is_openai_provider() else None,
            truncation="auto",
        ),
        conversation_starters=[
            "Generate a clean product hero image for my landing page.",
            "Edit this uploaded photo to match a cinematic style.",
            "Create two variants: one with Gemini and one with OpenAI image model.",
            "Combine these images into a polished ad creative.",
        ],
    )


if __name__ == "__main__":
    from agency_swarm import Agency
    Agency(create_image_generation_agent()).terminal_demo()
