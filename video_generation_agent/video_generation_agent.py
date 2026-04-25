from agency_swarm import Agent, ModelSettings
from agency_swarm.tools import LoadFileAttachment
from openai.types.shared.reasoning import Reasoning
from shared_tools import CopyFile

from config import get_default_model, is_openai_provider


def create_video_generation_agent() -> Agent:
    return Agent(
        name="Video Agent",
        description="A general-purpose agent for video generation and editing.",
        instructions="instructions.md",
        tools_folder="./tools",
        tools=[LoadFileAttachment, CopyFile],
        model=get_default_model(),
        model_settings=ModelSettings(
            reasoning=Reasoning(summary="auto", effort="medium") if is_openai_provider() else None,
            truncation="auto",
        ),
        conversation_starters=[
            "Generate a short promo video for my product launch.",
            "Create an animated explainer video about how AI works.",
            "Edit this video clip and add captions.",
            "Turn my blog post into a video with voiceover.",
        ],
    )
