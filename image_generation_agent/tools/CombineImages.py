"""Combine multiple image references into a single generated composition."""

from io import BytesIO
from typing import Literal

import os
from openai import OpenAI
from PIL import Image
from pydantic import Field, field_validator, model_validator

from agency_swarm import BaseTool
from run_utils import _load_openswarm_dotenv
from shared_tools.model_availability import image_model_availability_message
from shared_tools.openai_client_utils import get_openai_client

from .utils.image_io import (
    get_images_dir,
    build_variant_output_name,
    resolve_image_reference,
    save_image,
    image_to_base64_jpeg,
    build_multimodal_outputs,
    extract_gemini_image_and_usage,
    extract_openai_images_and_usage,
    run_parallel_variants_sync,
    validate_aspect_ratio_for_model,
    get_openai_size_for_aspect_ratio,
)


class CombineImages(BaseTool):
    """
    Combine multiple images into a single generated composition
    using the selected model and instruction.
    """

    product_name: str = Field(..., description="Product namespace for output files.")
    image_refs: list[str] = Field(
        ...,
        description="List of image references (URLs, absolute paths, or generated image names).",
    )
    text_instruction: str = Field(..., description="Instruction for how images should be combined.")
    output_file_name: str = Field(
        ...,
        description=(
            "Output image name (without extension) or output path. "
            "If a path is provided, the image is saved at that path."
        ),
    )
    model: Literal["gemini-2.5-flash-image", "gemini-3-pro-image-preview", "gpt-image-1.5"] = Field(
        default="gemini-2.5-flash-image",
        description="Image model to use for composition.",
    )
    aspect_ratio: Literal["1:1", "2:3", "3:2", "3:4", "4:3", "4:5", "5:4", "9:16", "16:9", "21:9"] = Field(
        default="1:1",
        description="Target aspect ratio. Model compatibility is validated automatically.",
    )
    num_variants: int = Field(default=1, description="Number of variants to generate (1-4).")

    @field_validator("product_name", "text_instruction", "output_file_name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value

    @field_validator("image_refs")
    @classmethod
    def _validate_refs(cls, value: list[str]) -> list[str]:
        if len(value) < 2:
            raise ValueError("image_refs must include at least two images")
        for item in value:
            if not item.strip():
                raise ValueError("image reference must not be empty")
        return value

    @field_validator("num_variants")
    @classmethod
    def _validate_variants(cls, value: int) -> int:
        if value < 1 or value > 4:
            raise ValueError("num_variants must be between 1 and 4")
        return value

    @model_validator(mode="after")
    def _validate_model_aspect_ratio(self) -> "CombineImages":
        validate_aspect_ratio_for_model(self.model, self.aspect_ratio)
        return self

    def run(self) -> list:
        _load_openswarm_dotenv(override=True)
        images_dir = get_images_dir(self.product_name)
        reference_images = [resolve_image_reference(self.product_name, ref)[0] for ref in self.image_refs]

        if self.model.startswith("gemini-"):
            results, usage_metadata = self._run_gemini(images_dir, reference_images)
            return build_multimodal_outputs(results, "Image composition complete")

        results, usage_metadata = self._run_openai(images_dir, reference_images)
        return build_multimodal_outputs(results, "Image composition complete")

    def _run_gemini(self, images_dir, reference_images: list[Image.Image]):
        from google import genai
        from google.genai.types import GenerateContentConfig, ImageConfig

        api_key = os.getenv("GOOGLE_API_KEY")
        if not api_key:
            raise ValueError(
                image_model_availability_message(
                    self,
                    failed_requirement="GOOGLE_API_KEY is not set. Gemini image composition requires the Google add-on key.",
                )
            )

        client = genai.Client(api_key=api_key)
        results: list[dict] = []
        total_prompt_tokens = 0.0
        total_candidate_tokens = 0.0

        def compose_single_variant(idx: int):
            response = client.models.generate_content(
                model=self.model,
                contents=[*reference_images, self.text_instruction],
                config=GenerateContentConfig(
                    image_config=ImageConfig(aspect_ratio=self.aspect_ratio),
                ),
            )
            image, usage = extract_gemini_image_and_usage(response)
            if image is None:
                return None

            variant_name = build_variant_output_name(self.output_file_name, idx, self.num_variants)
            image_name, file_path = save_image(image, variant_name, images_dir)
            return {
                "image_name": image_name,
                "file_path": file_path,
                "preview_b64": image_to_base64_jpeg(image),
                "prompt_tokens": float(usage.get("prompt_token_count") or 0),
                "candidate_tokens": float(usage.get("candidates_token_count") or 0),
            }

        raw_results = run_parallel_variants_sync(compose_single_variant, self.num_variants)
        if not raw_results:
            raise RuntimeError("Gemini did not return any composed images.")

        for item in raw_results:
            total_prompt_tokens += item.pop("prompt_tokens")
            total_candidate_tokens += item.pop("candidate_tokens")
            results.append(item)

        usage_metadata = {
            "prompt_token_count": total_prompt_tokens,
            "candidates_token_count": total_candidate_tokens,
        }
        return results, usage_metadata

    def _run_openai(self, images_dir, reference_images: list[Image.Image]):
        size = get_openai_size_for_aspect_ratio(self.aspect_ratio)

        input_buffers: list[BytesIO] = []
        for idx, image in enumerate(reference_images, start=1):
            buffer = BytesIO()
            image.save(buffer, format="PNG")
            buffer.seek(0)
            buffer.name = f"reference_{idx}.png"
            input_buffers.append(buffer)

        try:
            client = get_openai_client(tool=self)
            if not str(client.base_url).startswith("https://api.openai.com"):
                raise ValueError(
                    image_model_availability_message(
                        self,
                        failed_requirement=(
                            "The current auth is Codex/browser auth. gpt-image-1.5 composition is not supported through the Codex API."
                        ),
                    )
                )
            response = client.images.edit(
                model=self.model,
                image=input_buffers,
                prompt=self.text_instruction,
                size=size,
                n=self.num_variants,
            )
        finally:
            for buffer in input_buffers:
                buffer.close()

        images, usage_metadata = extract_openai_images_and_usage(response)
        if not images:
            raise RuntimeError("OpenAI image API did not return composed images.")

        results: list[dict] = []
        for idx, image in enumerate(images, start=1):
            variant_name = build_variant_output_name(self.output_file_name, idx, len(images))
            image_name, file_path = save_image(image, variant_name, images_dir)
            results.append(
                {
                    "image_name": image_name,
                    "file_path": file_path,
                    "preview_b64": image_to_base64_jpeg(image),
                }
            )
        return results, usage_metadata


if __name__ == "__main__":
    # Example test scenario
    tool = CombineImages(
        product_name="Test_Product",
        image_refs=["hero_image_example_oai", "edited_image_example"],
        text_instruction=(
            "Apply logo on a product. Keep the original product image as is."
        ),
        output_file_name="combined_example",
        model="gpt-image-1.5",
        aspect_ratio="1:1",
        num_variants=1,
    )
    try:
        result = tool.run()
        print(result)
    except Exception as exc:
        print(f"Image composition failed: {exc}")
