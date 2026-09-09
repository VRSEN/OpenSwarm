"""Shared utilities for Sora video tools."""

from __future__ import annotations

import io
import json
import logging
import os
import shutil
from pathlib import Path
from typing import Optional
from urllib.parse import urlparse

import httpx
from openai import OpenAI
from PIL import Image

from agency_swarm import ToolOutputText, ToolOutputImage
from shared_tools.model_availability import video_model_availability_message

from .image_utils import (
    load_image_by_name,
    get_images_dir,
    compress_image_for_base64,
    IMAGES_DIR,
)

logger = logging.getLogger(__name__)


SORA_MODEL = "sora-2"


def is_veo_model(model: str) -> bool:
    return model.startswith("veo-")


def is_sora_model(model: str) -> bool:
    return model.startswith("sora-")


def is_seedance_model(model: str) -> bool:
    return model.startswith("seedance-")


if os.path.isfile("/.dockerenv"):
    MNT_DIR = Path("/app/mnt")
else:
    MNT_DIR = Path(__file__).parent.parent.parent.parent / "mnt"

VIDEO_DIR = str(MNT_DIR / "generated_videos")  # fallback when no product_name is given


def get_videos_dir(product_name: str) -> str:
    """
    Get the videos directory for a specific product.
    
    Args:
        product_name: Name of the product (sanitized folder name)
        
    Returns:
        Path to product's generated_videos directory
    """
    videos_dir = MNT_DIR / product_name / "generated_videos"
    videos_dir.mkdir(parents=True, exist_ok=True)
    return str(videos_dir)


def resolve_ffmpeg_executable() -> str:
    """Resolve an ffmpeg executable from PATH or imageio-ffmpeg fallback."""
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        return ffmpeg_path

    try:
        from imageio_ffmpeg import get_ffmpeg_exe  # type: ignore

        ffmpeg_path = get_ffmpeg_exe()
        if ffmpeg_path:
            return ffmpeg_path
    except Exception:
        pass

    raise RuntimeError(
        "ffmpeg executable not found. Install ffmpeg and add it to PATH, "
        "or install the Python package 'imageio-ffmpeg' for bundled ffmpeg fallback."
    )


from shared_tools.openai_client_utils import get_openai_client


def get_gemini_client():
    """Instantiate a Gemini client from the environment."""
    from google import genai

    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise ValueError(
            video_model_availability_message(
                failed_requirement="GOOGLE_API_KEY is not set. Veo video generation requires the Google add-on key."
            )
        )
    return genai.Client(api_key=api_key)


def parse_video_size(size: str) -> tuple[int, int]:
    """
    Parse video size string into width and height tuple.
    
    Args:
        size: Size string in WIDTHxHEIGHT format (e.g. '1280x720')
    
    Returns:
        Tuple of (width, height)
    """
    parts = size.lower().split("x")
    if len(parts) != 2:
        raise ValueError(f"Invalid size format: {size}")
    return int(parts[0]), int(parts[1])


def resize_image_to_dimensions(image: Image.Image, width: int, height: int) -> Image.Image:
    """
    Resize an image to match specific dimensions while maintaining aspect ratio.
    
    Args:
        image: PIL Image to resize
        width: Target width
        height: Target height
    
    Returns:
        Resized PIL Image
    """
    # Calculate aspect ratios
    target_ratio = width / height
    image_ratio = image.width / image.height
    
    if abs(target_ratio - image_ratio) < 0.01:
        # Aspect ratios are close enough, just resize directly
        return image.resize((width, height), Image.Resampling.LANCZOS)
    
    # Aspect ratios differ, crop to match target ratio first
    if image_ratio > target_ratio:
        # Image is wider than target, crop width
        new_width = int(image.height * target_ratio)
        left = (image.width - new_width) // 2
        image = image.crop((left, 0, left + new_width, image.height))
    else:
        # Image is taller than target, crop height
        new_height = int(image.width / target_ratio)
        top = (image.height - new_height) // 2
        image = image.crop((0, top, image.width, top + new_height))
    
    # Now resize to exact dimensions
    return image.resize((width, height), Image.Resampling.LANCZOS)


def resolve_input_reference(reference: Optional[str], target_size: Optional[str] = None, product_name: Optional[str] = None) -> Optional[io.BufferedReader]:
    """
    Turn an image name, local path, or HTTPS URL into a binary file handle for the API.
    Optionally resizes the image to match target video dimensions.
    
    Args:
        reference: Image name (without extension), full path, or URL to the reference image
        target_size: Optional target size in WIDTHxHEIGHT format (e.g. '1280x720')
        product_name: Product name for locating images in product-specific folders
    
    Returns:
        Binary file handle ready for API upload
    """
    if reference is None:
        return None

    parsed = urlparse(reference)
    
    if parsed.scheme in ("http", "https"):
        # Handle URL
        logger.info("Downloading reference image from URL...")
        with httpx.Client(timeout=30.0) as client:
            response = client.get(reference)
            response.raise_for_status()
            image_data = io.BytesIO(response.content)
            filename = Path(parsed.path).name or "reference.png"
    else:
        # Try as full path first
        path = Path(reference).expanduser().resolve()
        
        if path.exists():
            # Handle full path
            logger.info(f"Loading reference image from {path}...")
            with open(path, "rb") as f:
                image_data = io.BytesIO(f.read())
            filename = path.name
        else:
            # Try as image name without extension in multiple directories
            pil_image = None
            image_path = None
            
            # Get product-specific directories
            if product_name:
                images_dir = get_images_dir(product_name)
                videos_dir = get_videos_dir(product_name)
            else:
                # Fallback to legacy paths if no product_name provided
                images_dir = IMAGES_DIR
                videos_dir = VIDEO_DIR
            
            # Try in generated_images directory first
            logger.info(f"Looking for image '{reference}' in {images_dir}...")
            pil_image, image_path, load_error_images = load_image_by_name(
                reference, images_dir, [".png", ".jpg", ".jpeg", ".webp"]
            )
            
            # If not found, try in generated_videos directory (for thumbnails/spritesheets)
            if load_error_images:
                logger.info(f"Not found in {images_dir}, trying {videos_dir}...")
                pil_image, image_path, load_error_videos = load_image_by_name(
                    reference, videos_dir, [".png", ".jpg", ".jpeg", ".webp"]
                )
            
            if pil_image is None:
                raise FileNotFoundError(f"Reference image '{reference}' not found in {images_dir} or {videos_dir}")
            
            logger.info(f"Loaded image: {image_path}")
            
            # Convert PIL Image to BytesIO
            image_data = io.BytesIO()
            pil_image.save(image_data, format=pil_image.format or "PNG")
            image_data.seek(0)
            filename = Path(image_path).name
    
    if target_size:
        logger.info(f"Resizing reference image to match video dimensions: {target_size}")
        image_data.seek(0)
        image = Image.open(image_data)
        
        # Get target dimensions
        width, height = parse_video_size(target_size)
        
        # Resize the image
        resized_image = resize_image_to_dimensions(image, width, height)
        
        # Save resized image to buffer
        buffer = io.BytesIO()
        # Preserve format or use PNG as default
        image_format = image.format or "PNG"
        resized_image.save(buffer, format=image_format)
        buffer.seek(0)
        buffer.name = filename
        
        logger.info(f"Reference image resized from {image.width}x{image.height} to {width}x{height}")
        return buffer  # type: ignore[return-value]
    
    image_data.seek(0)
    image_data.name = filename
    return image_data  # type: ignore[return-value]


def validate_resolution(value: Optional[str]) -> Optional[str]:
    """Ensure a resolution string is in WIDTHxHEIGHT format."""

    if value is None:
        return None
    parts = value.lower().split("x")
    if len(parts) != 2 or not all(part.isdigit() for part in parts):
        raise ValueError("size must be formatted as WIDTHxHEIGHT (e.g. 1280x720)")
    return value


def ensure_not_blank(value: str, field_name: str) -> str:
    """Raise if a text field is empty or whitespace only."""

    if not value.strip():
        raise ValueError(f"{field_name} must not be empty")
    return value


def download_video_variant(client: OpenAI, video_id: str, variant: str, output_path: str) -> None:
    """
    Download a specific variant of a video from Sora API.
    
    Args:
        client: OpenAI client instance
        video_id: The video ID from Sora API
        variant: Type of content to download (spritesheet, thumbnail, or video)
        output_path: Full path where the file should be saved
    """
    logger.info(f"Downloading {variant} for video {video_id}...")
    content = client.videos.download_content(video_id, variant=variant)
    content.write_to_file(output_path)


def create_image_output(image_path: str, label: str) -> list:
    """
    Create tool output objects for an image file.
    
    Args:
        image_path: Path to the image file
        label: Label to display for the image (filename)
    
    Returns:
        List containing ToolOutputText and ToolOutputImage objects
    """
    image = Image.open(image_path)
    compressed_b64 = compress_image_for_base64(image)
    
    return [
        ToolOutputText(type="text", text=f"{label}\nPath: {image_path}"),
        ToolOutputImage(type="image", image_url=f"data:image/png;base64,{compressed_b64}", detail="auto")
    ]


def extract_last_frame(video_path: str, output_path: str) -> Optional[Image.Image]:
    """
    Extract the last frame from a video file.
    
    Args:
        video_path: Path to the video file
        output_path: Path where the last frame image should be saved
    
    Returns:
        PIL Image object of the last frame, or None if extraction failed
    """
    import cv2  # lazy: defer native OpenCV import until actually needed (see #38)

    logger.info("Extracting last frame from video...")
    cap = cv2.VideoCapture(video_path)
    
    # Get total frame count and set to last frame
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    cap.set(cv2.CAP_PROP_POS_FRAMES, total_frames - 1)
    ret, frame = cap.read()
    
    cap.release()
    
    if not ret:
        return None
    
    # Convert BGR to RGB (OpenCV uses BGR)
    frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
    last_frame_image = Image.fromarray(frame_rgb)
    
    # Save last frame
    last_frame_image.save(output_path)
    
    return last_frame_image


def generate_spritesheet(video_path: str, output_path: str, frames_per_row: int = 6, num_rows: int = 1) -> Optional[Image.Image]:
    """
    Generate a linear spritesheet from a video file.
    
    Args:
        video_path: Path to the video file
        output_path: Path where the spritesheet should be saved
        frames_per_row: Number of frames in the spritesheet (default 6, range 4-7)
        num_rows: Number of rows (default 1 for linear layout)
    
    Returns:
        PIL Image object of the spritesheet, or None if generation failed
    """
    import cv2  # lazy: defer native OpenCV import until actually needed (see #38)

    logger.info("Generating spritesheet from video...")
    cap = cv2.VideoCapture(video_path)
    
    # Get total frame count
    total_frames = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    frame_width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    frame_height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    
    # Calculate frames to extract (evenly distributed)
    total_frames_needed = frames_per_row * num_rows
    frame_indices = [int(i * total_frames / total_frames_needed) for i in range(total_frames_needed)]
    
    # Extract frames
    frames = []
    for frame_idx in frame_indices:
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_idx)
        ret, frame = cap.read()
        if ret:
            # Convert BGR to RGB
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            frames.append(Image.fromarray(frame_rgb))
    
    cap.release()
    
    if not frames:
        return None
    
    # Calculate thumbnail size (smaller for spritesheet)
    thumb_width = frame_width // 4
    thumb_height = frame_height // 4
    
    # Create spritesheet
    spritesheet_width = thumb_width * frames_per_row
    spritesheet_height = thumb_height * num_rows
    spritesheet = Image.new('RGB', (spritesheet_width, spritesheet_height))
    
    # Paste frames into spritesheet
    for idx, frame in enumerate(frames):
        row = idx // frames_per_row
        col = idx % frames_per_row
        x = col * thumb_width
        y = row * thumb_height
        
        # Resize frame to thumbnail size
        frame_thumb = frame.resize((thumb_width, thumb_height), Image.Resampling.LANCZOS)
        spritesheet.paste(frame_thumb, (x, y))
    
    # Save spritesheet
    spritesheet.save(output_path, quality=85)
    logger.info(f"Spritesheet saved to {output_path}")
    
    return spritesheet


def download_veo_video(gemini_client, video_file, output_path: str) -> None:
    """
    Download a Veo video from Google Gemini API.
    
    Args:
        gemini_client: Google Gemini client instance
        video_file: Video file object from Gemini API
        output_path: Full path where the video should be saved
    """
    logger.info(f"Downloading Veo video to {output_path}...")
    gemini_client.files.download(file=video_file)
    video_file.save(output_path)


def save_veo_video_with_metadata(gemini_client, video_file, name: str, product_name: str) -> list:
    """
    Download and save Veo video with metadata (spritesheet, thumbnail, last frame).
    
    Args:
        gemini_client: Google Gemini client instance
        video_file: Video file object from Gemini API
        name: Base name for saved files (without extension)
        product_name: Name of the product (for organizing files in product-specific folders)
    
    Returns:
        List of ToolOutput objects showing the saved files
    """
    import cv2  # lazy: defer native OpenCV import until actually needed (see #38)

    output = []
    videos_dir = get_videos_dir(product_name)

    video_path = os.path.join(videos_dir, f"{name}.mp4")
    download_veo_video(gemini_client, video_file, video_path)

    spritesheet_path = os.path.join(videos_dir, f"{name}_spritesheet.jpg")
    generate_spritesheet(video_path, spritesheet_path)

    thumbnail_path = os.path.join(videos_dir, f"{name}_thumbnail.jpg")
    cap = cv2.VideoCapture(video_path)
    ret, frame = cap.read()
    if ret:
        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        Image.fromarray(frame_rgb).save(thumbnail_path)
    cap.release()

    last_frame_path = os.path.join(videos_dir, f"{name}_last_frame.jpg")
    extract_last_frame(video_path, last_frame_path)
    
    veo_reference = {}
    if getattr(video_file, "name", None):
        veo_reference["veo_video_ref"] = video_file.name
    if getattr(video_file, "uri", None):
        veo_reference["veo_video_uri"] = video_file.uri

    reference_path = None
    if veo_reference:
        reference_path = os.path.join(videos_dir, f"{name}_veo_reference.json")
        with open(reference_path, "w", encoding="utf-8") as handle:
            json.dump(veo_reference, handle, indent=2, ensure_ascii=True)

    summary_lines = [
        f"Video saved to `{name}.mp4`",
        f"Path: {video_path}",
    ]
    if veo_reference.get("veo_video_ref"):
        summary_lines.append(f"Veo reference: {veo_reference['veo_video_ref']}")
    if veo_reference.get("veo_video_uri"):
        summary_lines.append(f"Veo URI: {veo_reference['veo_video_uri']}")
    if reference_path:
        summary_lines.append(f"Reference file: {reference_path}")

    output.append(ToolOutputText(type="text", text="\n".join(summary_lines)))
    
    return output


def save_video_with_metadata(client: OpenAI, video_id: str, name: str, product_name: str) -> list:
    """
    Download and save video with all metadata (spritesheet, thumbnail, last frame).
    
    Args:
        client: OpenAI client instance
        video_id: The video ID from Sora API
        name: Base name for saved files (without extension)
        product_name: Name of the product (for organizing files in product-specific folders)
    
    Returns:
        List of ToolOutput objects showing the saved files
    """
    output = []
    videos_dir = get_videos_dir(product_name)

    spritesheet_path = os.path.join(videos_dir, f"{name}_spritesheet.jpg")
    download_video_variant(client, video_id, "spritesheet", spritesheet_path)

    thumbnail_path = os.path.join(videos_dir, f"{name}_thumbnail.jpg")
    download_video_variant(client, video_id, "thumbnail", thumbnail_path)

    video_path = os.path.join(videos_dir, f"{name}.mp4")
    download_video_variant(client, video_id, "video", video_path)

    last_frame_path = os.path.join(videos_dir, f"{name}_last_frame.jpg")
    extract_last_frame(video_path, last_frame_path)

    output.append(ToolOutputText(type="text", text=f"Video saved to `{name}.mp4`\nPath: {video_path}\nVideo ID: {video_id}"))
    
    return output
