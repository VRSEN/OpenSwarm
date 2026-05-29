"""Tool for editing images using Google's Gemini 2.5 Flash Image model."""

import asyncio
import os
from typing import Literal

from google import genai
from pydantic import Field, field_validator

from agency_swarm import BaseTool
from run_utils import _load_openswarm_dotenv
from shared_tools.model_availability import image_model_availability_message

from .utils.image_utils import (
    get_images_dir,
    MODEL_NAME,
    load_image_by_name,
    extract_image_from_response,
    extract_usage_metadata,
    process_variant_result,
    split_results_and_usage,
    run_parallel_variants,
    compress_image_for_base64,
)


class EditImage(BaseTool):
    """Edit existing images using Google's Gemini 2.5 Flash Image (Nano Banana) model.
    
    Images are saved to: mnt/{product_name}/generated_images/
    """

    product_name: str = Field(
        ...,
        description="Name of the product this image is for (e.g., 'Acme_Widget_Pro', 'Green_Tea_Extract'). Used to organize files into product-specific folders.",
    )
    input_image_name: str = Field(
        ...,
        description="Name of the existing image file to edit (without extension).",
    )
    edit_prompt: str = Field(
        ...,
        description="Text prompt describing the edits to make to the image",
    )
    output_image_name: str = Field(
        ...,
        description="The name for the generated edited image file (without extension)",
    )
    num_variants: int = Field(
        default=1,
        description="Number of image variants to generate (1-4, default is 1)",
    )
    aspect_ratio: Literal["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"] = Field(
        default="1:1",
        description="The aspect ratio of the generated image (default is 1:1)",
    )

    @field_validator("input_image_name")
    @classmethod
    def _input_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("input_image_name must not be empty")
        return value

    @field_validator("edit_prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("edit_prompt must not be empty")
        return value

    @field_validator("output_image_name")
    @classmethod
    def _output_name_not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("output_image_name must not be empty")
        return value

    @field_validator("num_variants")
    @classmethod
    def _validate_num_variants(cls, value: int) -> int:
        if value < 1 or value > 4:
            raise ValueError("num_variants must be between 1 and 4")
        return value

    async def run(self) -> list:
        """Edit an image using the Gemini API."""
        _load_openswarm_dotenv(override=True)
        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                image_model_availability_message(
                    self,
                    failed_requirement="GOOGLE_API_KEY is not set. Gemini image editing requires the Google add-on key.",
                )
            )

        client = genai.Client(api_key=api_key)
        images_dir = get_images_dir(self.product_name)

        image, _image_path, load_error = load_image_by_name(self.input_image_name, images_dir)
        if load_error:
            raise FileNotFoundError(load_error)

        def edit_single_variant(variant_num: int):
            try:
                response = client.models.generate_content(
                    model=MODEL_NAME,
                    contents=[self.edit_prompt, image],
                    config=genai.types.GenerateContentConfig(
                        image_config=genai.types.ImageConfig(aspect_ratio=self.aspect_ratio),
                    ),
                )
                usage_metadata = extract_usage_metadata(response)
                edited_image, _text = extract_image_from_response(response)
                if edited_image is None:
                    return None
                result = process_variant_result(
                    variant_num,
                    edited_image,
                    self.output_image_name,
                    self.num_variants,
                    compress_image_for_base64,
                    images_dir,
                )
                result["prompt_tokens"] = float(usage_metadata.get("prompt_token_count") or 0)
                result["candidate_tokens"] = float(usage_metadata.get("candidates_token_count") or 0)
                return result
            except Exception:
                return None

        raw_results = await run_parallel_variants(edit_single_variant, self.num_variants)
        if not raw_results:
            raise RuntimeError("No variants were successfully generated")

        results, _usage = split_results_and_usage(raw_results)
        return results

if __name__ == "__main__":
    # Example usage with Google Gemini 2.5 Flash Image
    tool = EditImage(
        product_name="Test_Product",
        input_image_name="logo_image_variant_1",
        edit_prompt="Change the logo color from red to blue",
        output_image_name="logo_image_edited",
        num_variants=1,
    )
    try:
        result = asyncio.run(tool.run())
        print(result)
    except Exception as exc:
        print(f"Image editing failed: {exc}")
