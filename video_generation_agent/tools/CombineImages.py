"""Tool for combining multiple images using Google's Gemini 2.5 Flash Image model."""

import io
from typing import Literal
from pathlib import Path

import os
from google import genai
from PIL import Image
from pydantic import Field, field_validator

from agency_swarm import BaseTool
from run_utils import _load_openswarm_dotenv
from shared_tools.model_availability import image_model_availability_message

from .utils.image_utils import (
    get_images_dir,
    MODEL_NAME,
    load_image_by_name,
    extract_image_parts_from_response,
    extract_usage_metadata,
    process_variant_result,
    split_results_and_usage,
    run_parallel_variants,
    compress_image_for_base64,
)


class CombineImages(BaseTool):
    """Combine multiple images using Google's Gemini 2.5 Flash Image (Nano Banana) model according to the given text instruction.
    
    Images are saved to: mnt/{product_name}/generated_images/
    """

    product_name: str = Field(
        ...,
        description="Name of the product these images are for (e.g., 'Acme_Widget_Pro', 'Green_Tea_Extract'). Used to organize files into product-specific folders.",
    )
    image_names: list[str] = Field(
        ...,
        description="List of image file names (without extension) or full file paths to combine. Can mix both formats.",
    )
    text_instruction: str = Field(
        ...,
        description="Text instruction describing how to combine the images",
    )
    file_name_or_path: str = Field(
        ...,
        description="The name (without extension) or full path for the generated combined image file",
    )
    num_variants: int = Field(
        default=1,
        description="Number of image variants to generate (1-4, default is 1)",
    )
    aspect_ratio: Literal["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"] = Field(
        default="1:1",
        description="The aspect ratio of the generated image (default is 1:1)",
    )

    @field_validator("image_names")
    @classmethod
    def _validate_image_names(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("image_names must not be empty")
        if len(value) < 2:
            raise ValueError("At least 2 images are required for combining")
        for name in value:
            if not name.strip():
                raise ValueError("Image names must not be empty")
        return value

    @field_validator("text_instruction")
    @classmethod
    def _instruction_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("text_instruction must not be empty")
        return value

    @field_validator("file_name_or_path")
    @classmethod
    def _filename_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("file_name_or_path must not be empty")
        return value

    @field_validator("num_variants")
    @classmethod
    def _validate_num_variants(cls, value: int) -> int:
        if value < 1 or value > 4:
            raise ValueError("num_variants must be between 1 and 4")
        return value

    async def run(self) -> list:
        """Combine images using the Gemini API."""
        _load_openswarm_dotenv(override=True)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                image_model_availability_message(
                    self,
                    failed_requirement="GOOGLE_API_KEY is not set. Gemini image composition requires the Google add-on key.",
                )
            )

        client = genai.Client(api_key=api_key)
        images_dir = get_images_dir(self.product_name)

        images = []
        for image_name_or_path in self.image_names:
            path = Path(image_name_or_path).expanduser().resolve()
            if path.exists():
                images.append(Image.open(path))
            else:
                image, _image_path, load_error = load_image_by_name(
                    image_name_or_path, images_dir, [".png", ".jpg", ".jpeg"]
                )
                if load_error:
                    raise FileNotFoundError(f"Image not found: '{image_name_or_path}' (tried as path and as name in {images_dir})")
                images.append(image)

        def combine_single_variant(variant_num: int):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=images + [self.text_instruction],
                    config=genai.types.GenerateContentConfig(
                        image_config=genai.types.ImageConfig(aspect_ratio=self.aspect_ratio),
                    ),
                )
                usage_metadata = extract_usage_metadata(response)
                image_parts = extract_image_parts_from_response(response)
                if not image_parts:
                    return None
                combined_image = Image.open(io.BytesIO(image_parts[0]))
                result = process_variant_result(
                    variant_num,
                    combined_image,
                    self.file_name_or_path,
                    self.num_variants,
                    compress_image_for_base64,
                    images_dir,
                )
                result["prompt_tokens"] = float(usage_metadata.get("prompt_token_count") or 0)
                result["candidate_tokens"] = float(usage_metadata.get("candidates_token_count") or 0)
                return result
            except Exception:
                return None

        raw_results = await run_parallel_variants(combine_single_variant, self.num_variants)
        if not raw_results:
            raise RuntimeError("No variants were successfully generated")

        results, _usage = split_results_and_usage(raw_results)
        return results

if __name__ == "__main__":
    # Example usage with Google Gemini 2.5 Flash Image
    import asyncio
    tool = CombineImages(
        product_name="Test_Product",
        image_names=["laptop_image_variant_2", "logo_image_variant_2"],
        text_instruction=(
            "Take the first image of a laptop on a table. Add the logo from the second image into the middle "
            "of the laptop. Remove the background of the logo and make it transparent. Ensure the laptop and "
            "features remain completely unchanged. The logo should look like it's naturally attached."
        ),
        file_name_or_path="laptop_with_logo",
        num_variants=2,
    )
    try:
        result = asyncio.run(tool.run())
        print(result)
    except Exception as exc:
        print(f"Image combining failed: {exc}")
