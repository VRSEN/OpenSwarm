"""Download an image into a project's assets folder."""

import ipaddress
from pathlib import Path
from urllib.parse import urlparse
from urllib.request import Request, urlopen

from agency_swarm.tools import BaseTool
from pydantic import Field

from .slide_file_utils import (
    IMAGE_CHUNK_SIZE,
    MAX_IMAGE_BYTES,
    get_project_dir,
    sanitize_image_filename,
    validate_project_name,
)

_BLOCKED_HOST_EXACT = frozenset(
    {"localhost", "169.254.169.254", "0.0.0.0", "::1", "::", "::ffff:127.0.0.1"}
)

_BLOCKED_HOST_PREFIXES = ("127.", "10.", "192.168.", "169.254.", "0.")

_SVG_XML_TYPES = frozenset({"text/xml", "application/xml"})


def _is_blocked_host(host: str | None) -> bool:
    if not host:
        return True
    name = host.strip().lower().rstrip(".")
    if not name:
        return True
    if name in _BLOCKED_HOST_EXACT or name.endswith(".localhost"):
        return True
    for prefix in _BLOCKED_HOST_PREFIXES:
        if name.startswith(prefix):
            return True
    if name.startswith("172."):
        try:
            second = int(name.split(".")[1])
        except (IndexError, ValueError):
            second = -1
        if 16 <= second <= 31:
            return True
    if name.isdigit():
        try:
            if not ipaddress.ip_address(int(name)).is_global:
                return True
        except ValueError:
            return True
    try:
        if not ipaddress.ip_address(name).is_global:
            return True
    except ValueError:
        pass
    return False


def _read_bounded(response, limit: int = MAX_IMAGE_BYTES) -> bytes:
    data = bytearray()
    while True:
        chunk = response.read(IMAGE_CHUNK_SIZE)
        if not chunk:
            break
        data.extend(chunk)
        if len(data) > limit:
            raise ValueError(
                f"Error: image exceeds size limit ({limit} bytes)."
            )
    return bytes(data)


class DownloadImage(BaseTool):
    """
    Download an image from a URL into the project's assets folder.
    """

    project_name: str = Field(..., description="Name of the presentation project")
    url: str = Field(..., description="Image URL to download")
    image_name: str = Field(..., description="Desired filename (with or without extension)")

    def run(self) -> str:
        try:
            validate_project_name(self.project_name)
        except ValueError as exc:
            return str(exc)

        try:
            file_name = sanitize_image_filename(self.image_name, self.url)
        except ValueError as exc:
            return str(exc)

        project_dir = get_project_dir(self.project_name)
        assets_dir = project_dir / "assets"
        assets_dir.mkdir(parents=True, exist_ok=True)

        parsed = urlparse(self.url)
        if parsed.scheme not in ("http", "https"):
            return "Error: URL must start with http or https."
        if _is_blocked_host(parsed.hostname):
            return "Error: URL host is blocked (loopback, private, or metadata address)."

        output_path = assets_dir / file_name
        try:
            resolved_assets = assets_dir.resolve()
            resolved_output = output_path.resolve()
        except Exception as exc:
            return f"Error: could not resolve output path: {exc}"
        if not resolved_output.is_relative_to(resolved_assets):
            return "Error: image_name must stay inside the project assets folder (blocked path traversal)."

        try:
            request = Request(self.url, headers={"User-Agent": "slides_agent/1.0"})
            with urlopen(request, timeout=30) as response:
                headers = getattr(response, "headers", None)
                length_raw = None
                content_type = ""
                if headers is not None:
                    try:
                        length_raw = headers.get("Content-Length")
                        content_type = headers.get("Content-Type", "") or ""
                    except Exception:
                        length_raw, content_type = None, ""
                else:
                    getter = getattr(response, "getheader", None)
                    if callable(getter):
                        try:
                            length_raw = getter("Content-Length")
                            content_type = getter("Content-Type") or ""
                        except Exception:
                            length_raw, content_type = None, ""
                if length_raw not in (None, ""):
                    try:
                        if int(str(length_raw).strip()) > MAX_IMAGE_BYTES:
                            return (
                                "Error: image exceeds size limit "
                                f"({MAX_IMAGE_BYTES} bytes)."
                            )
                    except (TypeError, ValueError):
                        pass
                media_type = content_type.split(";")[0].strip().lower()
                if media_type:
                    if output_path.suffix.lower() == ".svg":
                        if not (media_type.startswith("image/") or media_type in _SVG_XML_TYPES):
                            return (
                                "Error: URL did not return an image "
                                f"(Content-Type: {media_type or 'unknown'})."
                            )
                    elif not media_type.startswith("image/"):
                        return (
                            "Error: URL did not return an image "
                            f"(Content-Type: {media_type or 'unknown'})."
                        )
                try:
                    content = _read_bounded(response)
                except ValueError as exc:
                    return str(exc)
            # Reject HTML or non-image content (e.g. error pages)
            if content.lstrip()[:100].lower().startswith((b"<!doctype", b"<html", b"< ")):
                return "Error: URL did not return an image (got HTML). Use a direct image URL or try another source."
            output_path.write_bytes(content)
            # Verify we can read it as an image (SVGs are validated separately)
            if output_path.suffix.lower() == ".svg":
                snippet = content.lstrip()[:200].lower()
                if b"<svg" not in snippet and b"<?xml" not in snippet:
                    output_path.unlink(missing_ok=True)
                    return "Error: Downloaded file is not a valid SVG. Use a direct image URL or try another source."
            else:
                try:
                    from PIL import Image
                    with Image.open(output_path) as img:
                        img.verify()
                except Exception:
                    output_path.unlink(missing_ok=True)
                    return "Error: Downloaded file is not a valid image. Use a direct image URL (e.g. .jpg, .png) or try another source."
        except Exception as exc:
            return f"Error downloading image: {exc}"

        return f"Downloaded image to: {output_path}"

    def _ensure_extension(self, image_name: str, url: str) -> str:
        return sanitize_image_filename(image_name, url)


if __name__ == "__main__":
    tool = DownloadImage(
        project_name="openclaw_presentation_v3",
        url="https://raw.githubusercontent.com/openclaw/openclaw/main/docs/assets/sponsors/convex.svg",
        image_name="sponsor_convex.svg"
    )
    print(tool.run())
