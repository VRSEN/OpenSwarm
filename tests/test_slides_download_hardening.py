"""Regression tests: harden slides DownloadImage (path traversal + SSRF + size caps)."""

import base64
import importlib.util
import sys
import types
from pathlib import Path
from unittest.mock import patch

REPO = Path(__file__).resolve().parent.parent

# 1x1 transparent PNG fallback when PIL is unavailable.
_TINY_PNG = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
)


def _valid_png_bytes() -> bytes:
    try:
        from PIL import Image
        import io

        buf = io.BytesIO()
        Image.new("RGB", (1, 1), color="red").save(buf, format="PNG")
        return buf.getvalue()
    except Exception:
        return _TINY_PNG


def _install_stubs() -> None:
    agency = types.ModuleType("agency_swarm")
    agency_tools = types.ModuleType("agency_swarm.tools")

    class BaseTool:
        def __init__(self, **kwargs):
            for key, value in kwargs.items():
                setattr(self, key, value)

    agency_tools.BaseTool = BaseTool
    agency.tools = agency_tools

    pydantic = types.ModuleType("pydantic")

    def Field(default=None, **_kwargs):  # noqa: N802 - match pydantic API
        return default

    pydantic.Field = Field
    pydantic.ValidationError = ValueError

    sys.modules["agency_swarm"] = agency
    sys.modules["agency_swarm.tools"] = agency_tools
    sys.modules["pydantic"] = pydantic


def _load_modules():
    _install_stubs()
    for name in (
        "slides_agent",
        "slides_agent.tools",
        "slides_agent.tools.slide_file_utils",
        "slides_agent.tools.DownloadImage",
    ):
        sys.modules.pop(name, None)

    pkg = types.ModuleType("slides_agent")
    pkg.__path__ = [str(REPO / "slides_agent")]
    tools_pkg = types.ModuleType("slides_agent.tools")
    tools_pkg.__path__ = [str(REPO / "slides_agent" / "tools")]
    sys.modules["slides_agent"] = pkg
    sys.modules["slides_agent.tools"] = tools_pkg

    spec_utils = importlib.util.spec_from_file_location(
        "slides_agent.tools.slide_file_utils",
        REPO / "slides_agent" / "tools" / "slide_file_utils.py",
    )
    utils = importlib.util.module_from_spec(spec_utils)
    sys.modules[spec_utils.name] = utils
    assert spec_utils and spec_utils.loader
    spec_utils.loader.exec_module(utils)

    spec_dl = importlib.util.spec_from_file_location(
        "slides_agent.tools.DownloadImage",
        REPO / "slides_agent" / "tools" / "DownloadImage.py",
    )
    download = importlib.util.module_from_spec(spec_dl)
    sys.modules[spec_dl.name] = download
    assert spec_dl and spec_dl.loader
    spec_dl.loader.exec_module(download)
    return utils, download


class _FakeHeaders(dict):
    def get(self, key, default=None):
        return super().get(key, default)


class _FakeResponse:
    def __init__(self, payload: bytes, content_type="image/png", length=None):
        self._payload = payload
        self._offset = 0
        headers = _FakeHeaders()
        headers["Content-Type"] = content_type
        headers["Content-Length"] = str(len(payload) if length is None else length)
        self.headers = headers

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, size=-1):
        if size is None or size < 0:
            size = len(self._payload) - self._offset
        chunk = self._payload[self._offset : self._offset + size]
        self._offset += len(chunk)
        return chunk


def _tool(download, tmp_path, **kwargs):
    kwargs.setdefault("project_name", "demo")
    download.get_project_dir = (
        lambda name: tmp_path / name / "presentations"  # noqa: ARG005
    )
    return download.DownloadImage(**kwargs)


def test_traversal_rejected(tmp_path):
    _, download = _load_modules()
    png = _valid_png_bytes()
    with patch.object(
        download, "urlopen", return_value=_FakeResponse(png)
    ) as mocked:
        tool = _tool(
            download,
            tmp_path,
            url="https://example.com/a.png",
            image_name="../../escape.png",
        )
        result = tool.run()
    assert result.startswith("Error:")
    assert "traversal" in result.lower() or "separators" in result.lower()
    mocked.assert_not_called()
    assert not (tmp_path / "escape.png").exists()
    assert list((tmp_path).rglob("escape.png")) == []


def test_absolute_path_rejected(tmp_path):
    _, download = _load_modules()
    png = _valid_png_bytes()
    with patch.object(
        download, "urlopen", return_value=_FakeResponse(png)
    ) as mocked:
        tool = _tool(
            download,
            tmp_path,
            url="https://example.com/a.png",
            image_name="/tmp/evil.png",
        )
        result = tool.run()
    assert result.startswith("Error:")
    mocked.assert_not_called()


def test_bad_extension_rejected(tmp_path):
    _, download = _load_modules()
    png = _valid_png_bytes()
    with patch.object(
        download, "urlopen", return_value=_FakeResponse(png)
    ) as mocked:
        tool = _tool(
            download,
            tmp_path,
            url="https://example.com/payload.exe",
            image_name="payload.exe",
        )
        result = tool.run()
    assert result.startswith("Error:")
    assert "extension" in result.lower()
    mocked.assert_not_called()


def test_oversized_content_length_rejected(tmp_path):
    utils, download = _load_modules()
    png = _valid_png_bytes()
    oversized = utils.MAX_IMAGE_BYTES + 1
    with patch.object(
        download,
        "urlopen",
        return_value=_FakeResponse(png, length=oversized),
    ) as mocked:
        tool = _tool(
            download,
            tmp_path,
            url="https://example.com/big.png",
            image_name="big.png",
        )
        result = tool.run()
    assert result.startswith("Error:")
    assert "size limit" in result.lower()
    mocked.assert_called_once()
    assert list(tmp_path.rglob("big.png")) == []


def test_chunked_oversize_without_length_rejected(tmp_path):
    utils, download = _load_modules()
    big = b"\x89PNG\r\n\x1a\n" + b"A" * (utils.MAX_IMAGE_BYTES + 1)

    class _NoLength(_FakeResponse):
        def __init__(self):
            self._payload = big
            self._offset = 0
            self.headers = _FakeHeaders({"Content-Type": "image/png"})

    with patch.object(download, "urlopen", return_value=_NoLength()):
        tool = _tool(
            download,
            tmp_path,
            url="https://example.com/big2.png",
            image_name="big2.png",
        )
        result = tool.run()
    assert result.startswith("Error:")
    assert "size limit" in result.lower()


def test_ssrf_hosts_blocked(tmp_path):
    _, download = _load_modules()
    for url in (
        "http://localhost/image.png",
        "http://127.0.0.1/image.png",
        "http://10.0.0.5/image.png",
        "http://192.168.1.10/image.png",
        "http://169.254.169.254/latest/meta-data/",
        "http://[::1]/image.png",
    ):
        with patch.object(download, "urlopen") as mocked:
            tool = _tool(
                download, tmp_path, url=url, image_name="ok.png"
            )
            result = tool.run()
        assert result.startswith("Error:"), url
        assert "blocked" in result.lower(), url
        mocked.assert_not_called()


def test_valid_mocked_png_accepted(tmp_path):
    _, download = _load_modules()
    png = _valid_png_bytes()
    with patch.object(
        download, "urlopen", return_value=_FakeResponse(png)
    ):
        tool = _tool(
            download,
            tmp_path,
            url="https://example.com/a.png",
            image_name="hero",
        )
        result = tool.run()
    assert result.startswith("Downloaded image to:")
    saved = tmp_path / "demo" / "presentations" / "assets" / "hero.png"
    assert saved.exists()
    assert saved.read_bytes() == png


def test_sanitize_helper_rejects_traversal():
    utils, _ = _load_modules()
    for bad in ("../../x.png", "..\\x.png", "/abs/x.png", "", "run.sh", "page.html"):
        try:
            utils.sanitize_image_filename(bad, "https://example.com/a.png")
        except ValueError as exc:
            assert str(exc).startswith("Error:")
        else:
            raise AssertionError(f"expected rejection for {bad!r}")
    assert utils.sanitize_image_filename("hero", "https://example.com/a.png") == "hero.png"
    assert (
        utils.sanitize_image_filename("pic", "https://example.com/p.jpeg") == "pic.jpeg"
    )
