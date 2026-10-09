import base64
import concurrent.futures
import io
import os
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests
from PIL import Image

from agency_swarm import ToolOutputImage, ToolOutputText


DEFAULT_EXTENSIONS = (".png", ".jpg", ".jpeg", ".webp")
ALL_ASPECT_RATIOS = (
    "1:1",
    "2:3",
    "3:2",
    "3:4",
    "4:3",
    "4:5",
    "5:4",
    "9:16",
    "16:9",
    "21:9",
)
SUPPORTED_ASPECT_RATIOS_BY_MODEL = {
    "gemini-2.5-flash-image": set(ALL_ASPECT_RATIOS),
    "gemini-3-pro-image-preview": set(ALL_ASPECT_RATIOS),
    # OpenAI image API size options are:
    # 1024x1024 (1:1), 1024x1536 (2:3), 1536x1024 (3:2)
    "gpt-image-2.5-sunburst": {"1:1", "2:3", "3:2"},
}
OPENAI_SIZE_BY_ASPECT_RATIO = {
    "1:1": "1024x1024",
    "2:3": "1024x1536",
    "3:2": "1536x1024",
}

if os.path.isfile("/.dockerenv"):
    MNT_DIR = Path("/app/mnt")
else:
    MNT_DIR = Path(__file__).parent.parent.parent.parent / "mnt"


def get_images_dir(product_name: str) -> Path:
    images_dir = MNT_DIR / product_name / "generated_images"
    images_dir.mkdir(parents=True, exist_ok=True)
    return images_dir


def find_image_path_from_name(images_dir: Path, image_name: str) -> Path | None:
    for ext in DEFAULT_EXTENSIONS:
        candidate = images_dir / f"{image_name}{ext}"
        if candidate.exists():
            return candidate
    return None


def resolve_image_reference(product_name: str, image_ref: str) -> tuple[Image.Image, str]:
    if not image_ref.strip():
        raise ValueError("image reference must not be empty")

    parsed = urlparse(image_ref)
    if parsed.scheme in ("http", "https"):
        response = requests.get(image_ref, timeout=30)
        response.raise_for_status()
        image = Image.open(io.BytesIO(response.content))
        return image.convert("RGB"), image_ref

    candidate_path = Path(image_ref).expanduser().resolve()
    if candidate_path.exists():
        image = Image.open(candidate_path)
        return image.convert("RGB"), str(candidate_path)

    images_dir = get_images_dir(product_name)
    by_name = find_image_path_from_name(images_dir, image_ref)
    if by_name is not None:
        image = Image.open(by_name)
        return image.convert("RGB"), str(by_name)

    raise FileNotFoundError(
        f"Could not resolve image reference '{image_ref}' as URL, path, or name in {images_dir}."
    )


_IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".gif", ".bmp", ".tiff"}


def normalize_file_name(value: str) -> str:
    """Strip a known image extension from the name, but leave other dots untouched.

    "hero.png"   → "hero"
    "5.1_no_bg"  → "5.1_no_bg"  (dot is part of the name, not an extension)
    """
    name = value.strip()
    if not name:
        raise ValueError("file name must not be empty")
    p = Path(name)
    return p.stem if p.suffix.lower() in _IMAGE_EXTENSIONS else name


def build_variant_output_name(output_name: str, variant_index: int, total_variants: int) -> str:
    raw_value = output_name.strip()
    if not raw_value:
        raise ValueError("output name must not be empty")
    if total_variants <= 1:
        return raw_value

    candidate = Path(raw_value)
    has_image_ext = candidate.suffix.lower() in _IMAGE_EXTENSIONS
    if has_image_ext:
        variant_file = f"{candidate.stem}_variant_{variant_index}{candidate.suffix}"
        return str(candidate.with_name(variant_file))

    return f"{raw_value}_variant_{variant_index}"


def save_image(image: Image.Image, output_name: str, images_dir: Path) -> tuple[str, str]:
    raw_value = output_name.strip()
    candidate = Path(raw_value).expanduser()

    has_image_ext = candidate.suffix.lower() in _IMAGE_EXTENSIONS
    has_path_sep = any(sep in raw_value for sep in ("/", "\\"))

    if has_image_ext:
        output_path = candidate if candidate.is_absolute() else images_dir / candidate
        image_name = output_path.stem
    elif has_path_sep:
        output_path = candidate if candidate.is_absolute() else images_dir / candidate
        output_path = output_path.with_suffix(".png")
        image_name = output_path.stem
    else:
        image_name = normalize_file_name(raw_value)
        output_path = images_dir / f"{image_name}.png"

    output_path.parent.mkdir(parents=True, exist_ok=True)
    image.save(output_path, format="PNG")
    return image_name, str(output_path)


def image_to_base64_jpeg(
    image: Image.Image,
    max_size: int = 768,
    target_bytes: int = 120_000,
    min_quality: int = 45,
) -> str:
    """
    Create a compact JPEG preview for multimodal outputs.

    This intentionally optimizes for small payload size to reduce token costs.
    """
    rgb = image.convert("RGB")
    width, height = rgb.size

    if max(width, height) > max_size:
        scale = max_size / max(width, height)
        rgb = rgb.resize((int(width * scale), int(height * scale)), Image.Resampling.LANCZOS)

    best_bytes: bytes | None = None
    work = rgb
    quality_steps = (80, 70, 62, 55, min_quality)

    # Try lowering JPEG quality first.
    for quality in quality_steps:
        buffer = io.BytesIO()
        work.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
        candidate = buffer.getvalue()
        if best_bytes is None or len(candidate) < len(best_bytes):
            best_bytes = candidate
        if len(candidate) <= target_bytes:
            return base64.b64encode(candidate).decode("utf-8")

    # If still too large, iteratively downscale and retry quality steps.
    while max(work.size) > 320:
        next_size = (max(1, int(work.width * 0.85)), max(1, int(work.height * 0.85)))
        work = work.resize(next_size, Image.Resampling.LANCZOS)
        for quality in quality_steps:
            buffer = io.BytesIO()
            work.save(buffer, format="JPEG", quality=quality, optimize=True, progressive=True)
            candidate = buffer.getvalue()
            if best_bytes is None or len(candidate) < len(best_bytes):
                best_bytes = candidate
            if len(candidate) <= target_bytes:
                return base64.b64encode(candidate).decode("utf-8")

    # Final fallback: return the smallest candidate we produced.
    assert best_bytes is not None
    return base64.b64encode(best_bytes).decode("utf-8")


def build_multimodal_outputs(items: list[dict[str, Any]], title: str) -> list:
    lines = [f"{title}: {len(items)} image(s)"]
    for item in items:
        lines.append(f"- {item['image_name']}: {item['file_path']}")

    outputs: list = [ToolOutputText(type="text", text="\n".join(lines))]
    for item in items:
        outputs.append(ToolOutputText(type="text", text=f"Path: {item['file_path']}"))
        outputs.append(
            ToolOutputImage(
                type="image",
                image_url=f"data:image/jpeg;base64,{item['preview_b64']}",
                detail="auto",
            )
        )
    return outputs


def extract_gemini_image_and_usage(response: Any) -> tuple[Image.Image | None, dict]:
    image: Image.Image | None = None
    usage = getattr(response, "usage_metadata", {}) or {}

    if usage and not isinstance(usage, dict):
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        elif hasattr(usage, "__dict__"):
            usage = vars(usage)
        else:
            try:
                usage = dict(usage)
            except (TypeError, ValueError):
                usage = {}

    candidates = getattr(response, "candidates", None) or []
    for candidate in candidates:
        content = getattr(candidate, "content", None)
        parts = getattr(content, "parts", None) or []
        for part in parts:
            inline_data = getattr(part, "inline_data", None)
            if inline_data and getattr(inline_data, "data", None):
                image = Image.open(io.BytesIO(inline_data.data)).convert("RGB")
                return image, usage

    parts = getattr(response, "parts", None) or []
    for part in parts:
        inline_data = getattr(part, "inline_data", None)
        if inline_data and getattr(inline_data, "data", None):
            image = Image.open(io.BytesIO(inline_data.data)).convert("RGB")
            return image, usage

    return None, usage


def extract_openai_images_and_usage(response: Any) -> tuple[list[Image.Image], dict]:
    usage = getattr(response, "usage", {}) or {}
    if usage and not isinstance(usage, dict):
        if hasattr(usage, "model_dump"):
            usage = usage.model_dump()
        elif hasattr(usage, "__dict__"):
            usage = vars(usage)
        else:
            try:
                usage = dict(usage)
            except (TypeError, ValueError):
                usage = {}

    images: list[Image.Image] = []
    data = getattr(response, "data", None) or []
    for item in data:
        b64 = getattr(item, "b64_json", None)
        if b64:
            raw = base64.b64decode(b64)
            images.append(Image.open(io.BytesIO(raw)).convert("RGB"))

    return images, usage


def run_parallel_variants_sync(task_fn, num_variants: int) -> list:
    results_by_index: dict[int, Any] = {}
    with concurrent.futures.ThreadPoolExecutor(max_workers=num_variants) as executor:
        future_to_index = {
            executor.submit(task_fn, idx): idx
            for idx in range(1, num_variants + 1)
        }
        for future in concurrent.futures.as_completed(future_to_index):
            idx = future_to_index[future]
            try:
                result = future.result()
                if result is not None:
                    results_by_index[idx] = result
            except Exception:
                pass

    return [results_by_index[idx] for idx in sorted(results_by_index.keys())]


def validate_aspect_ratio_for_model(model: str, aspect_ratio: str) -> None:
    supported = SUPPORTED_ASPECT_RATIOS_BY_MODEL.get(model)
    if supported is None:
        raise ValueError(f"Unsupported model: {model}")
    if aspect_ratio not in supported:
        raise ValueError(
            f"Aspect ratio '{aspect_ratio}' is not supported by model '{model}'. "
            f"Supported values: {sorted(supported)}"
        )


def get_openai_size_for_aspect_ratio(aspect_ratio: str) -> str:
    size = OPENAI_SIZE_BY_ASPECT_RATIO.get(aspect_ratio)
    if not size:
        raise ValueError(
            f"Aspect ratio '{aspect_ratio}' cannot be mapped to an OpenAI image size. "
            f"Supported values: {sorted(OPENAI_SIZE_BY_ASPECT_RATIO.keys())}"
        )
    return size

