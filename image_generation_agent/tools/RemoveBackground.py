"""Remove image backgrounds using the Pixelcut model via fal.ai."""

import io
import os
from pathlib import Path
from urllib.parse import urlparse

import fal_client
import requests
from PIL import Image
from pydantic import Field, field_validator

from agency_swarm import BaseTool
from run_utils import _load_openswarm_dotenv
from shared_tools.model_availability import image_model_availability_message

from .utils.image_io import (
    find_image_path_from_name,
    get_images_dir,
    save_image,
)

FAL_ENDPOINT = "pixelcut/background-removal"


class RemoveBackground(BaseTool):
    """
    Remove the background from an image using Pixelcut via fal.ai.

    The output is a transparent PNG saved to: mnt/{product_name}/generated_images/
    Supports local path, URL, or generated image name as input.
    """

    product_name: str = Field(..., description="Product namespace for output files.")
    input_image_ref: str = Field(
        ...,
        description="Input image reference (URL, absolute path, or generated image name).",
    )
    output_file_name: str = Field(
        ...,
        description=(
            "Output image name (without extension) or output path. "
            "If a path is provided, the image is saved at that path."
        ),
    )

    @field_validator("product_name", "input_image_ref", "output_file_name")
    @classmethod
    def _not_blank(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("value must not be empty")
        return value

    def run(self) -> list:
        _load_openswarm_dotenv(override=True)
        api_key = os.getenv("FAL_KEY")
        if not api_key:
            raise ValueError(
                image_model_availability_message(
                    self,
                    failed_requirement="FAL_KEY is not set. Background removal requires the fal.ai add-on key.",
                )
            )
        fal = fal_client.SyncClient(key=api_key)

        images_dir = get_images_dir(self.product_name)
        image_url = self._resolve_to_upload_url(images_dir, fal)
        result = fal.subscribe(
            FAL_ENDPOINT,
            arguments={"image_url": image_url, "output_format": "rgba", "sync_mode": False},
        )

        result_url = (result.get("image") or {}).get("url")
        if not result_url:
            raise RuntimeError("fal.ai background removal returned no image URL.")

        rgba_image = self._download_rgba(result_url)
        image_name, file_path = save_image(rgba_image, self.output_file_name, images_dir)

        return f"Background removal complete.\nImage name: {image_name}\nPath: {file_path}"

    def _resolve_to_upload_url(self, images_dir: Path, fal: fal_client.SyncClient) -> str:
        ref = self.input_image_ref.strip()

        parsed = urlparse(ref)
        if parsed.scheme in ("http", "https"):
            return ref

        candidate = Path(ref).expanduser().resolve()
        if candidate.exists():
            return fal.upload_file(str(candidate))

        by_name = find_image_path_from_name(images_dir, ref)
        if by_name is not None:
            return fal.upload_file(str(by_name))

        raise FileNotFoundError(
            f"Could not resolve image reference '{ref}' as URL, path, or name in {images_dir}."
        )

    def _download_rgba(self, url: str) -> Image.Image:
        response = requests.get(url, timeout=30)
        response.raise_for_status()
        return Image.open(io.BytesIO(response.content)).convert("RGBA")

if __name__ == "__main__":
    tool = RemoveBackground(
        product_name="Test_Product",
        input_image_ref="test_image.jpg",
        output_file_name="hero_no_bg",
    )
    try:
        result = tool.run()
        print(result)
    except Exception as exc:
        print(f"Background removal failed: {exc}")
