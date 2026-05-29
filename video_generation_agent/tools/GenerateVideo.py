"""Video generation tool supporting Sora (OpenAI), Veo (Google Gemini), and Seedance (fal.ai) models."""

from typing import Literal, Optional
import asyncio
import logging
import os
import re
import mimetypes
from pathlib import Path
from urllib.parse import urlparse

import fal_client
import httpx
from openai import OpenAI
from pydantic import Field, field_validator, model_validator
from google.genai.types import GenerateVideosConfig, Image, VideoGenerationReferenceImage
from PIL import Image as PILImage
from io import BytesIO

from agency_swarm import BaseTool, ToolOutputText
from run_utils import _load_openswarm_dotenv
from shared_tools.model_availability import video_model_availability_message
from shared_tools.openai_client_utils import get_openai_client

from .utils.video_utils import (
    ensure_not_blank,
    extract_last_frame,
    generate_spritesheet,
    get_gemini_client,
    get_videos_dir,
    is_veo_model,
    is_sora_model,
    is_seedance_model,
    resolve_input_reference,
    validate_resolution,
    save_video_with_metadata,
    save_veo_video_with_metadata,
)
from .utils.image_utils import load_image_by_name, get_images_dir

logger = logging.getLogger(__name__)

VIDEO_GENERATION_TIMEOUT_SECONDS = 300


def _is_transient_network_error(exc: Exception) -> bool:
    if isinstance(exc, (BrokenPipeError, ConnectionResetError, TimeoutError)):
        return True

    message = str(exc).lower()
    transient_markers = (
        "broken pipe",
        "connection reset",
        "timed out",
        "timeout",
        "temporarily unavailable",
    )
    return any(marker in message for marker in transient_markers)


class GenerateVideo(BaseTool):
    """
    Generates a video using OpenAI Sora, Google Veo, or ByteDance Seedance 1.5 Pro (via fal.ai).

    Tool is stateless and does not maintain any characters / scenes / etc between calls.
    It does not support variables like [INTERNAL PROMPT] in the prompt.

    **Important**: Sora 2 and Sora 2 Pro do not support reference images with faces.

    Videos are saved to: mnt/{product_name}/generated_videos/
    """
    product_name: str = Field(
        ...,
        description="Name of the product this video is for (e.g., 'Acme_Widget_Pro', 'Green_Tea_Extract'). Used to organize files into product-specific folders.",
    )
    prompt: str = Field(
        ...,
        description=(
            "Detailed marketing description of the desired video. Include subjects, "
            "camera motion, lighting, and mood for the video generation model. "
            "Be ware that sometimes including things you DONT want to display in the video "
            "can cause the model to generate them instead. Simply don't mention what you don't want to see in the prompt."
        ),
    )
    name: str = Field(
        ...,
        description="The name for the generated video file (without extension)",
    )
    model: Literal[
        "sora-2",
        "sora-2-pro",
        "veo-3.1-generate-preview",
        "veo-3.1-fast-generate-preview",
        "seedance-1.5-pro",
    ] = Field(
        ...,
        description="Video generation model to use.",
    )
    seconds: int = Field(
        default=8,
        ge=4,
        le=12,
        description=(
            "Clip length in seconds. "
            "Sora: 4, 8, or 12. "
            "Veo: 4, 6, or 8. "
            "Seedance 1.5 Pro: any integer 4–12."
        ),
    )
    first_frame_ref: Optional[str] = Field(
        default=None,
        description=(
            "Optional first frame reference image for image-to-video. Can be: "
            "1) Image name without extension (searches generated_images and generated_videos folders), "
            "2) Full local path, or 3) HTTPS URL."
        ),
    )
    asset_image_ref: Optional[str] = Field(
        default=None,
        description=(
            "Optional asset reference image for Veo (subject/asset guidance). Can be: "
            "1) Image name without extension (searches generated_images and generated_videos folders), "
            "2) Full local path, or 3) HTTPS URL."
        ),
    )
    size: Literal['720x1280', '1280x720', '1024x1792', '1792x1024'] = Field(
        default='1280x720',
        description="Optional resolution in WIDTHxHEIGHT format (e.g. 1280x720). For Sora: exact resolution. For Veo: reference image will be cropped/resized to match this aspect ratio to prevent stretching.",
    )

    @field_validator("prompt")
    @classmethod
    def _prompt_not_blank(cls, value: str) -> str:
        if re.match(r"^\[.*\]", value) or re.match(r"^\[.*?\]\s+.+", value):
            raise ValueError("PROMPT CANNNOT CONTAIN VARIABLES!!! YOU HAVE TO REWRITE THE WHOLE PROMPT FROM SCRATCH!!! THIS TOOL IS STATELESS. STOP BEING LAZY AND REWRITE THE WHOLE PROMPT FOR USER'S FEEDBACK.")
        return ensure_not_blank(value, "prompt")

    @field_validator("first_frame_ref")
    @classmethod
    def _reference_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            ensure_not_blank(value, "first_frame_ref")
        return value

    @field_validator("asset_image_ref")
    @classmethod
    def _asset_reference_not_blank(cls, value: Optional[str]) -> Optional[str]:
        if value is not None:
            ensure_not_blank(value, "asset_image_ref")
        return value

    @field_validator("size")
    @classmethod
    def _size_format(cls, value: Optional[str]) -> Optional[str]:
        return validate_resolution(value)

    @model_validator(mode="after")
    def _validate_seconds_for_model(self) -> "GenerateVideo":
        if is_sora_model(self.model) and self.seconds not in {4, 8, 12}:
            raise ValueError("Sora supports only 4, 8, or 12 second clips.")
        if is_veo_model(self.model) and self.seconds not in {4, 6, 8}:
            raise ValueError("Veo supports only 4, 6, or 8 second clips.")
        if is_sora_model(self.model) and self.asset_image_ref is not None:
            raise ValueError("Sora does not support asset_image_ref. Use first_frame_ref instead.")
        if is_seedance_model(self.model) and self.asset_image_ref is not None:
            raise ValueError("Seedance does not support asset_image_ref. Use first_frame_ref instead.")
        return self

    async def run(self) -> list:
        """Generate a marketing video using the chosen model."""
        _load_openswarm_dotenv(override=True)
        if is_seedance_model(self.model):
            return await self._generate_with_seedance(self.model)

        if is_sora_model(self.model):
            return await self._generate_with_sora(self.model)

        if is_veo_model(self.model):
            return await self._generate_with_veo(self.model)

        raise ValueError(f"Unsupported video model: {self.model}")

    async def _generate_with_sora(self, model: str) -> dict:
        """Generate video using OpenAI's Sora API."""

        client = get_openai_client(tool=self)
        if not str(client.base_url).startswith("https://api.openai.com"):
            raise ValueError(
                video_model_availability_message(
                    self,
                    failed_requirement=(
                        "The current auth is Codex/browser auth. Sora video generation is not supported through the Codex API."
                    ),
                )
            )
        reference_file = None
        
        try:
            reference_file = resolve_input_reference(
                self.first_frame_ref,
                target_size=self.size if self.first_frame_ref else None,
                product_name=self.product_name
            )

            request_payload = {
                "prompt": self.prompt,
                "model": model,
                "seconds": str(self.seconds),
            }
            if self.size:
                request_payload["size"] = self.size
            if reference_file is not None:
                request_payload["input_reference"] = reference_file

            logger.info(f"Submitting video generation request to Sora ({model})...")
            
            # Run blocking operation in thread pool to avoid blocking event loop
            loop = asyncio.get_event_loop()
            try:
                video = await loop.run_in_executor(
                    None,
                    lambda: client.videos.create(**request_payload)
                )
            except Exception as exc:
                if _is_transient_network_error(exc):
                    raise RuntimeError(
                        f"Sora submission hit a transient network error: {exc}. "
                        "Please retry this GenerateVideo call."
                    ) from exc
                raise

            started_at = asyncio.get_running_loop().time()
            while getattr(video, "status", None) not in {"completed", "failed", "cancelled"}:
                logger.info("Waiting for Sora video generation to complete...")
                elapsed = asyncio.get_running_loop().time() - started_at
                if elapsed > VIDEO_GENERATION_TIMEOUT_SECONDS:
                    raise RuntimeError(
                        f"Sora video generation timed out after {VIDEO_GENERATION_TIMEOUT_SECONDS} seconds. Openai server is likely overloaded."
                        "Please try again later or use a different model."
                    )
                await asyncio.sleep(10)
                try:
                    video = await loop.run_in_executor(
                        None,
                        lambda: client.videos.retrieve(video.id)
                    )
                except Exception as exc:
                    if not _is_transient_network_error(exc):
                        raise
                    logger.warning(f"Transient Sora polling error: {exc}. Retrying same video id...")

            logger.info(f"Video generation status: {video.status}")
            if video.status != "completed":
                raise RuntimeError(
                    f"Sora video generation ended with status: {video.status}. Please retry."
                )

            return save_video_with_metadata(client, video.id, self.name, self.product_name)

        finally:
            if reference_file is not None and hasattr(reference_file, "close"):
                try:
                    reference_file.close()
                except Exception:
                    pass

    async def _generate_with_veo(self, model: str) -> dict:
        """Generate video using Google's Veo API with optional references."""

        client = get_gemini_client()
        
        try:
            config_kwargs = {"duration_seconds": self.seconds}
            first_frame_image = None
            
            # Add aspect_ratio and resolution only when NOT using reference images
            # (these parameters cause "not supported" errors when used with reference images)
            if self.size and not self.first_frame_ref and not self.asset_image_ref:
                width, height = map(int, self.size.split('x'))
                config_kwargs["aspect_ratio"] = "9:16" if width < height else "16:9"
            
            if self.asset_image_ref:
                parsed = urlparse(self.asset_image_ref)
                
                if parsed.scheme in ("http", "https"):
                    raise ValueError("Veo does not support URL reference images. Please use local images.")
                else:
                    path = Path(self.asset_image_ref).expanduser().resolve()
                    if path.exists():
                        image_path = str(path)
                    else:
                        images_dir = get_images_dir(self.product_name)
                        pil_image, image_path, load_error = load_image_by_name(
                            self.asset_image_ref, images_dir, [".png", ".jpg", ".jpeg", ".webp"]
                        )
                        if load_error:
                            raise FileNotFoundError(f"Reference image '{self.asset_image_ref}' not found in {images_dir}")
                
                logger.info(f"Loading asset reference image for Veo: {image_path}")
                
                with PILImage.open(image_path) as img:
                    if img.mode != 'RGB':
                        img = img.convert('RGB')

                    if self.size:
                        target_width, target_height = map(int, self.size.split('x'))
                        target_ratio = target_width / target_height
                        img_ratio = img.width / img.height
                        
                        # Crop to match aspect ratio (center crop)
                        if img_ratio > target_ratio:
                            # Image is wider, crop width
                            new_width = int(img.height * target_ratio)
                            left = (img.width - new_width) // 2
                            img = img.crop((left, 0, left + new_width, img.height))
                        elif img_ratio < target_ratio:
                            # Image is taller, crop height
                            new_height = int(img.width / target_ratio)
                            top = (img.height - new_height) // 2
                            img = img.crop((0, top, img.width, top + new_height))
                        
                        img = img.resize((target_width, target_height), PILImage.Resampling.LANCZOS)

                    buffer = BytesIO()
                    img.save(buffer, format='PNG')
                    image_bytes = buffer.getvalue()
                    mime_type = "image/png"

                config_kwargs["reference_images"] = [
                    VideoGenerationReferenceImage(
                        image=Image(
                            image_bytes=image_bytes,
                            mime_type=mime_type,
                        ),
                        reference_type="asset",
                    ),
                ]

            if self.first_frame_ref:
                # For first frame, pass as 'image' parameter directly to generate_videos()
                # According to official docs: https://docs.cloud.google.com/vertex-ai/generative-ai/docs/video/generate-videos-from-an-image
                reference_file = resolve_input_reference(
                    self.first_frame_ref,
                    target_size=self.size if self.first_frame_ref else None,
                    product_name=self.product_name,
                )
                first_frame_bytes = reference_file.read()
                mime_type = "image/png"
                if getattr(reference_file, "name", None):
                    guessed = mimetypes.guess_type(reference_file.name)[0]
                    if guessed:
                        mime_type = guessed
                
                first_frame_image = Image(
                    image_bytes=first_frame_bytes,
                    mime_type=mime_type,
                )
                
                if hasattr(reference_file, "close"):
                    try:
                        reference_file.close()
                    except Exception:
                        pass
            
            config = GenerateVideosConfig(**config_kwargs)
            
            if self.size and self.first_frame_ref:
                logger.info(f"Submitting video generation request to Veo ({model}) - first frame resized to {self.size} (aspect ratio inferred from image)...")
            elif self.size:
                logger.info(f"Submitting video generation request to Veo ({model}) - size: {self.size}...")
            else:
                logger.info(f"Submitting video generation request to Veo ({model})...")
            
            # run_in_executor keeps the event loop free while Veo polls
            loop = asyncio.get_event_loop()
            generate_kwargs = {
                "model": model,
                "prompt": self.prompt,
                "config": config,
            }
            
            # Add image parameter if first_frame_ref is provided (simple image-to-video)
            if first_frame_image:
                generate_kwargs["image"] = first_frame_image

            started_at = asyncio.get_running_loop().time()
            try:
                operation = await loop.run_in_executor(
                    None,
                    lambda: client.models.generate_videos(**generate_kwargs)
                )
            except Exception as exc:
                if _is_transient_network_error(exc):
                    raise RuntimeError(
                        f"Veo submission hit a transient network error: {exc}. "
                        "Please retry this GenerateVideo call."
                    ) from exc
                raise
            
            # Poll the operation status until the video is ready
            while not operation.done:
                logger.info("Waiting for Veo video generation to complete...")
                elapsed = asyncio.get_running_loop().time() - started_at
                if elapsed > VIDEO_GENERATION_TIMEOUT_SECONDS:
                    raise RuntimeError(
                        f"Veo video generation timed out after {VIDEO_GENERATION_TIMEOUT_SECONDS} seconds."
                    )
                await asyncio.sleep(10)
                try:
                    operation = await loop.run_in_executor(
                        None,
                        lambda: client.operations.get(operation)
                    )
                except Exception as exc:
                    if not _is_transient_network_error(exc):
                        raise
                    logger.warning(f"Transient Veo polling error: {exc}. Retrying same operation...")
            
            logger.info("Video generation complete!")
            
            # Download the generated video — retry on transient network errors
            generated_video = operation.response.generated_videos[0]
            MAX_DOWNLOAD_RETRIES = 3
            last_exc: Exception | None = None
            for attempt in range(MAX_DOWNLOAD_RETRIES):
                try:
                    output = await loop.run_in_executor(
                        None,
                        lambda: save_veo_video_with_metadata(
                            client, generated_video.video, self.name, self.product_name
                        ),
                    )
                    last_exc = None
                    break
                except Exception as exc:
                    last_exc = exc
                    if attempt < MAX_DOWNLOAD_RETRIES - 1 and _is_transient_network_error(exc):
                        wait = 5 * (attempt + 1)
                        logger.warning(
                            f"Transient Veo download error (attempt {attempt + 1}/{MAX_DOWNLOAD_RETRIES}): "
                            f"{exc}. Retrying in {wait}s..."
                        )
                        await asyncio.sleep(wait)
                    else:
                        raise
            if last_exc is not None:
                raise last_exc

            return output
            
        except RuntimeError:
            raise
        except Exception as e:
            raise RuntimeError(f"Veo video generation failed: {str(e)}")

    async def _generate_with_seedance(self, model: str) -> list:
        """Generate video using ByteDance Seedance 1.5 Pro via fal.ai."""
        api_key = os.getenv("FAL_KEY")
        if not api_key:
            raise ValueError(
                video_model_availability_message(
                    self,
                    failed_requirement="FAL_KEY is not set. Seedance video generation requires the fal.ai add-on key.",
                )
            )
        fal = fal_client.SyncClient(key=api_key)

        duration = str(self.seconds)

        # Map size → fal.ai resolution label and aspect ratio
        width, height = map(int, self.size.split("x"))
        max_dim = max(width, height)
        if max_dim >= 1080:
            resolution = "1080p"
        elif max_dim >= 720:
            resolution = "720p"
        else:
            resolution = "480p"

        if width < height:
            aspect_ratio = "9:16"
        elif width > height:
            aspect_ratio = "16:9"
        else:
            aspect_ratio = "1:1"

        if self.first_frame_ref:
            endpoint = "fal-ai/bytedance/seedance/v1.5/pro/image-to-video"
            image_url = await self._resolve_image_for_fal(self.first_frame_ref, fal)
            arguments: dict = {
                "prompt": self.prompt,
                "image_url": image_url,
                "duration": duration,
                "resolution": resolution,
            }
        else:
            endpoint = "fal-ai/bytedance/seedance/v1.5/pro/text-to-video"
            arguments = {
                "prompt": self.prompt,
                "duration": duration,
                "resolution": resolution,
                "aspect_ratio": aspect_ratio,
            }

        logger.info(f"Submitting video generation request to Seedance 1.5 Pro (fal.ai, {endpoint})...")
        result = await asyncio.to_thread(
            fal.subscribe, endpoint, arguments=arguments, with_logs=True
        )

        output_url = (result.get("video") or {}).get("url")
        if not output_url:
            raise RuntimeError(f"Seedance did not return a video URL. Response: {result}")

        videos_dir = get_videos_dir(self.product_name)
        output_path = os.path.join(videos_dir, f"{self.name}.mp4")

        logger.info(f"Downloading Seedance video to {output_path}...")
        async with httpx.AsyncClient(timeout=120.0) as http:
            response = await http.get(output_url)
            response.raise_for_status()
        with open(output_path, "wb") as fh:
            fh.write(response.content)

        spritesheet_path = os.path.join(videos_dir, f"{self.name}_spritesheet.jpg")
        await asyncio.to_thread(generate_spritesheet, output_path, spritesheet_path)

        last_frame_path = os.path.join(videos_dir, f"{self.name}_last_frame.jpg")
        await asyncio.to_thread(extract_last_frame, output_path, last_frame_path)

        return [ToolOutputText(type="text", text=f"Video saved to `{self.name}.mp4`\nPath: {output_path}")]

    async def _resolve_image_for_fal(self, image_ref: str, fal: fal_client.SyncClient) -> str:
        """Resolve a local path or image name to a fal.ai-accessible URL."""
        parsed = urlparse(image_ref)
        if parsed.scheme in ("http", "https"):
            return image_ref

        path = Path(image_ref).expanduser().resolve()
        if not path.exists():
            images_dir = get_images_dir(self.product_name)
            _, image_path, err = load_image_by_name(
                image_ref, images_dir, [".png", ".jpg", ".jpeg", ".webp"]
            )
            if err:
                raise FileNotFoundError(
                    f"Reference image '{image_ref}' not found in {images_dir}"
                )
            path = Path(image_path)

        return await asyncio.to_thread(fal.upload_file, str(path))

if __name__ == "__main__":
    # Basic test invocation (Sora)
    tool = GenerateVideo(
        product_name = "bird_forest_veo",
        prompt = "Cinematic nature footage: a small colorful songbird (robin-like) flies swiftly through a dense evergreen forest corridor, weaving between mossy trunks and sunlit branches. The camera follows in a smooth tracking shot at bird height, slightly behind and to the side, maintaining the bird in sharp focus while the background streaks with gentle motion blur. Early morning golden light filters through the canopy, creating volumetric rays and floating dust motes; rich greens and warm highlights, high dynamic range, natural filmic contrast. The bird beats its wings rhythmically, occasionally gliding past ferns and hanging vines; leaves flutter from the air wake. Lens: 35mm, shallow depth of field, stabilized gimbal-like motion, realistic textures and feathers. Audio: clear forest ambience with soft wind through needles, subtle wing flaps, distant birdsong.",
        name = "bird_flying_forest_4s_16x9_fast_v2",
        model = "veo-3.1-fast-generate-preview",
        seconds = 4,
        size = "1280x720"

    )
    try:
        logging.basicConfig(level=logging.INFO)
        result = asyncio.run(tool.run())
        print(result)
    except Exception as exc:
        print(f"Video generation failed: {exc}")
