"""Search images across Unsplash, Pexels, and Pixabay."""

from __future__ import annotations

import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen

import os
from agency_swarm.tools import BaseTool
from pydantic import Field
from run_utils import _load_openswarm_dotenv


class ImageSearch(BaseTool):
    """
    Search for existing images on the internet. Use this when the user wants to find real photos, diagrams, or illustrations of something rather than generating new images.
    Do not use this tool to find specific logos, icons, or other brand-specific images. It only provides generic images that are not brand-specific.
    """

    query: str = Field(
        ...,
        description="Image search query",
    )
    per_page: int = Field(
        default=6,
        description="Number of results per provider",
    )
    providers: list[str] | None = Field(
        default=None,
        description="Providers to search: unsplash, pexels, pixabay",
    )

    def run(self) -> str:
        _load_openswarm_dotenv(override=True)
        providers = [p.lower() for p in (self.providers or ["unsplash", "pexels", "pixabay"])]
        results = []
        warnings = []
        if "unsplash" in providers:
            key = os.getenv("UNSPLASH_ACCESS_KEY")
            if not key:
                warnings.append("Unsplash skipped: UNSPLASH_ACCESS_KEY not set.")
            else:
                url = "https://api.unsplash.com/search/photos?" + urlencode({
                    "query": self.query,
                    "per_page": self.per_page,
                })
                req = Request(url, headers={"Authorization": f"Client-ID {key}"})
                with urlopen(req, timeout=20) as response:
                    data = json.loads(response.read().decode("utf-8"))
                for item in data.get("results", []):
                    results.append({
                        "source": "unsplash",
                        "image_url": item.get("urls", {}).get("regular"),
                        "thumbnail_url": item.get("urls", {}).get("thumb"),
                        "description": item.get("description") or item.get("alt_description") or "",
                        "photographer": (item.get("user") or {}).get("name"),
                        "width": item.get("width"),
                        "height": item.get("height"),
                        "link": item.get("links", {}).get("html"),
                    })

        if "pexels" in providers:
            key = os.getenv("PEXELS_API_KEY")
            if not key:
                warnings.append("Pexels skipped: PEXELS_API_KEY not set.")
            else:
                url = "https://api.pexels.com/v1/search?" + urlencode({
                    "query": self.query,
                    "per_page": self.per_page,
                })
                req = Request(url, headers={"Authorization": key})
                with urlopen(req, timeout=20) as response:
                    data = json.loads(response.read().decode("utf-8"))
                for item in data.get("photos", []):
                    results.append({
                        "source": "pexels",
                        "image_url": (item.get("src") or {}).get("large"),
                        "thumbnail_url": (item.get("src") or {}).get("tiny"),
                        "description": item.get("alt") or "",
                        "photographer": item.get("photographer"),
                        "width": item.get("width"),
                        "height": item.get("height"),
                        "link": item.get("url"),
                    })

        if "pixabay" in providers:
            key = os.getenv("PIXABAY_API_KEY")
            if not key:
                warnings.append("Pixabay skipped: PIXABAY_API_KEY not set.")
            else:
                url = "https://pixabay.com/api/?" + urlencode({
                    "key": key,
                    "q": self.query,
                    "per_page": self.per_page,
                })
                req = Request(url)
                with urlopen(req, timeout=20) as response:
                    data = json.loads(response.read().decode("utf-8"))
                for item in data.get("hits", []):
                    results.append({
                        "source": "pixabay",
                        "image_url": item.get("largeImageURL"),
                        "thumbnail_url": item.get("previewURL"),
                        "description": item.get("tags") or "",
                        "photographer": item.get("user"),
                        "width": item.get("imageWidth"),
                        "height": item.get("imageHeight"),
                        "link": item.get("pageURL"),
                    })

        if not results:
            if len(warnings) == len(providers):
                raise ValueError(
                    "No image source keys are set. Add at least one of "
                    "UNSPLASH_ACCESS_KEY, PEXELS_API_KEY, or PIXABAY_API_KEY to your .env to use ImageSearch."
                )
            return f"No images found for '{self.query}'."

        return json.dumps({
            "query": self.query,
            "results": results,
            "warnings": warnings,
        }, indent=2)


if __name__ == "__main__":
    tool = ImageSearch(query="abstract digital technology mesh background")
    print(tool.run())
