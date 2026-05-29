"""Generate images using AI models for diagrams and concept art."""

from typing import Literal, Optional
import asyncio
import inspect

import os
from agency_swarm.tools import BaseTool, LoadFileAttachment
from pydantic import Field
from run_utils import _load_openswarm_dotenv
from shared_tools.model_availability import image_model_availability_message


class GenerateImage(BaseTool):
    """
    Generate images using Google Gemini models.
    
    Supports two modes:
    - Complex Diagrams (Flowcharts, Pyramids, Org Charts): Uses nano-banana-pro (gemini-3-pro-image-preview) optimized for text rendering
    - Concept Art (Illustrations, Atmosphere): Uses nano-banana (gemini-2.5-flash-image) for faster generation
    
    The generated image is saved to the specified output path or to the project's assets folder.
    """

    prompt: str = Field(
        ...,
        description="Detailed description of the image to generate. Be specific about layout, colors, style, and any text that should appear."
    )
    image_type: Literal["diagram", "concept_art"] = Field(
        ...,
        description="Type of image: 'diagram' for flowcharts/org charts (uses nano-banana-pro), 'concept_art' for illustrations"
    )
    project_name: str = Field(
        ...,
        description="Name of the presentation project (e.g. 'my_presentation'). The image is saved to that project's assets folder."
    )
    asset_name: str = Field(
        ...,
        description="Filename for the generated image including extension (e.g. 'hero.png'). Saved under the project's assets/ folder."
    )
    width: int = Field(
        default=1024,
        description="Image width in pixels (default 1024)"
    )
    height: int = Field(
        default=1024,
        description="Image height in pixels (default 1024)"
    )
    style: Optional[str] = Field(
        default=None,
        description="Optional style modifier (e.g., 'minimalist', 'professional', 'hand-drawn', 'technical')"
    )

    def run(self) -> str:
        """Generate image and save to the project's assets folder."""
        _load_openswarm_dotenv(override=True)
        from .slide_file_utils import get_project_dir
        try:
            full_prompt = self.prompt
            if self.style:
                full_prompt = f"{self.prompt} Style: {self.style}"

            if self.image_type == "diagram":
                model = "gemini-3-pro-image-preview"
                full_prompt = f"Technical diagram: {full_prompt}. Clear labels, professional layout, high contrast."
            else:
                model = "gemini-2.5-flash-image"
                full_prompt = f"High-quality illustration: {full_prompt}"

            image_data = self._generate_with_gemini(full_prompt, model)

            assets_dir = get_project_dir(self.project_name) / "assets"
            assets_dir.mkdir(parents=True, exist_ok=True)
            output = assets_dir / self.asset_name
            
            # Compress image to reduce token usage
            from PIL import Image
            import io
            
            # Load image from bytes
            img = Image.open(io.BytesIO(image_data))
            
            # Resize to 75% if larger than 1024px on any dimension
            if img.width > 1024 or img.height > 1024:
                new_size = (int(img.width * 0.75), int(img.height * 0.75))
                img = img.resize(new_size, Image.Resampling.LANCZOS)
            
            # Save with JPEG quality 80 for good balance
            img.save(output, 'JPEG', quality=80, optimize=True)

            # Return image as file attachment
            attachment = LoadFileAttachment(path=str(output))
            result = self._run_attachment(attachment)
            return f"Image saved to ./assets/{self.asset_name}\n\n{result}"
        
        except Exception as e:
            return f"Error generating image: {e}"
    
    def _run_attachment(self, attachment):
        """Run the attachment tool, handling async if needed."""
        result = attachment.run()
        if not inspect.isawaitable(result):
            return result

        try:
            asyncio.get_running_loop()
        except RuntimeError:
            return asyncio.run(result)

        new_loop = asyncio.new_event_loop()
        try:
            return new_loop.run_until_complete(result)
        finally:
            new_loop.close()

    def _generate_with_gemini(self, prompt: str, model: str) -> bytes:
        """Generate image using Google Gemini API (nano-banana or nano-banana-pro)."""
        try:
            from google import genai
            from google.genai.types import GenerateContentConfig, ImageConfig
            
            api_key = os.getenv("GOOGLE_API_KEY")
            if not api_key:
                raise ValueError(
                    image_model_availability_message(
                        self,
                        failed_requirement="GOOGLE_API_KEY is not set. Gemini image generation requires the Google add-on key.",
                    )
                )
            
            client = genai.Client(api_key=api_key)

            # Determine aspect ratio based on width/height
            aspect_ratio = "1:1"  # default square
            if self.width != self.height:
                # Calculate approximate aspect ratio
                ratio = self.width / self.height
                if abs(ratio - 16/9) < 0.1:
                    aspect_ratio = "16:9"
                elif abs(ratio - 9/16) < 0.1:
                    aspect_ratio = "9:16"
                elif abs(ratio - 4/3) < 0.1:
                    aspect_ratio = "4:3"
                elif abs(ratio - 3/4) < 0.1:
                    aspect_ratio = "3:4"
                elif abs(ratio - 3/2) < 0.1:
                    aspect_ratio = "3:2"
                elif abs(ratio - 2/3) < 0.1:
                    aspect_ratio = "2:3"
            
            # Configure image generation
            config = GenerateContentConfig(
                image_config=ImageConfig(
                    aspect_ratio=aspect_ratio,
                )
            )
            
            # Generate image
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config=config
            )
            
            # Extract image data from response
            if response.parts:
                for part in response.parts:
                    if hasattr(part, 'inline_data') and part.inline_data:
                        usage_metadata = getattr(response, "usage_metadata", {}) or {}
                        if usage_metadata and not isinstance(usage_metadata, dict):
                            if hasattr(usage_metadata, "model_dump"):
                                usage_metadata = usage_metadata.model_dump()
                            elif hasattr(usage_metadata, "__dict__"):
                                usage_metadata = vars(usage_metadata)
                            else:
                                try:
                                    usage_metadata = dict(usage_metadata)
                                except (TypeError, ValueError):
                                    usage_metadata = {}
                        return part.inline_data.data
            
            raise RuntimeError("No image data in response")
            
        except ImportError:
            raise RuntimeError("Google GenAI package not installed. Please install: pip install google-genai")
        except Exception as e:
            raise RuntimeError(f"Failed to generate image with Gemini: {e}")

if __name__ == "__main__":
    tool = GenerateImage(
        prompt="A flowchart showing a three-step process: Research -> Design -> Implementation. Use blue boxes and arrows.",
        image_type="concept_art",
        project_name="slides_agent_test_deck",
        asset_name="test_diagram.png",
        style="professional"
    )
    print(tool.run())
