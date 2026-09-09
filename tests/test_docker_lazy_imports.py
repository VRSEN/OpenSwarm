"""Regression test for #38: Docker SIGILL + misleading FastAPI auth warning.

- Video tools must not import native-heavy modules (cv2, google.genai,
  moviepy, numpy) at module top level, otherwise Agency Swarm agency
  construction (`create_agency()` during FastAPI startup) can die with
  SIGILL (exit 132) under QEMU / CPUs without the assumed SIMD features.
- server.py must accept API_TOKEN as an alias for APP_TOKEN.
"""

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent

LAZY_MODULES = ("cv2", "google", "moviepy", "numpy")

TOP_LEVEL_CHECK_FILES = [
    "video_generation_agent/tools/utils/video_utils.py",
    "video_generation_agent/tools/TrimVideo.py",
    "video_generation_agent/tools/EditAudio.py",
    "video_generation_agent/tools/EditVideoContent.py",
    "video_generation_agent/tools/GenerateVideo.py",
    "video_generation_agent/tools/CombineImages.py",
    "video_generation_agent/tools/EditImage.py",
    "video_generation_agent/tools/GenerateImage.py",
    "video_generation_agent/tools/AddSubtitles.py",
]


def _top_level_heavy_imports(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    found = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            for alias in node.names:
                root = alias.name.split(".")[0]
                if root in ("cv2", "moviepy", "numpy") or alias.name.startswith("google"):
                    found.append(alias.name)
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            root = module.split(".")[0]
            if root in ("cv2", "moviepy", "numpy", "google"):
                found.append(module)
    return found


def test_no_top_level_native_imports():
    offenders = {}
    for rel in TOP_LEVEL_CHECK_FILES:
        path = REPO / rel
        assert path.exists(), f"expected file missing: {rel}"
        heavy = _top_level_heavy_imports(path)
        if heavy:
            offenders[rel] = heavy
    assert not offenders, f"top-level heavy imports would run at agency construction: {offenders}"


def test_heavy_imports_are_lazy_where_needed():
    """Spot-check that the deferred imports still exist inside functions."""
    checks = {
        "video_generation_agent/tools/utils/video_utils.py": ("import cv2", "from google import genai"),
        "video_generation_agent/tools/TrimVideo.py": ("import cv2",),
        "video_generation_agent/tools/GenerateVideo.py": ("from google.genai.types import",),
        "video_generation_agent/tools/AddSubtitles.py": ("from moviepy.editor import", "import numpy"),
    }
    for rel, markers in checks.items():
        text = (REPO / rel).read_text(encoding="utf-8")
        for marker in markers:
            assert marker in text, f"{rel} should lazily import ({marker}) inside a function"


def test_server_accepts_api_token_alias():
    text = (REPO / "server.py").read_text(encoding="utf-8")
    assert "API_TOKEN" in text
    assert "APP_TOKEN" in text
    # Must not map model keys to HTTP auth.
    assert "OPENAI_API_KEY" in text


def test_dockerfile_pins_python312_and_blas_guards():
    text = (REPO / "Dockerfile").read_text(encoding="utf-8")
    assert "python:3.12-slim-bookworm" in text
    for var in ("OPENBLAS_CORETYPE=Haswell", "OPENBLAS_NUM_THREADS=1", "OMP_NUM_THREADS=1"):
        assert var in text, f"Dockerfile missing BLAS guard {var}"


def test_env_example_documents_token_alias():
    text = (REPO / ".env.example").read_text(encoding="utf-8")
    assert "APP_TOKEN" in text
    assert "API_TOKEN" in text
