import base64
import sys
import os
from pathlib import Path
from types import ModuleType
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]

# stub cairosvg before importing html_docx modules (mirrors test_html_docx_images.py)
def _stub_svg2png(**_):
    return b""

cairosvg = ModuleType("cairosvg")
cairosvg.svg2png = _stub_svg2png
sys.modules["cairosvg"] = cairosvg

# stub playwright to avoid heavy dependency during import
playwright_mod = ModuleType("playwright")
sync_api_mod = ModuleType("playwright.sync_api")
def _fake_sync_playwright():
    class _FakeBrowser:
        def new_page(self, *a, **kw): raise RuntimeError("should be mocked")
        def close(self): pass
    class _FakeChromium:
        def launch(self, *a, **kw):
            return _FakeBrowser()
    class _FakePlaywright:
        chromium = _FakeChromium()
        def __enter__(self): return self
        def __exit__(self, *a): return False
        def close(self): pass
    return _FakePlaywright()
sync_api_mod.sync_playwright = _fake_sync_playwright
sys.modules["playwright"] = playwright_mod
sys.modules["playwright.sync_api"] = sync_api_mod

for package_name, package_path in (
    ("docs_agent", ROOT / "docs_agent"),
    ("docs_agent.tools", ROOT / "docs_agent" / "tools"),
    ("docs_agent.tools.utils", ROOT / "docs_agent" / "tools" / "utils"),
):
    package = ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules.setdefault(package_name, package)

# Import after stubbing
from docs_agent.tools.utils.html_docx_images import _load_image_stream, _MAX_IMAGE_BYTES  # noqa: E402
from docs_agent.tools.utils.html_docx_core import html_to_docx  # noqa: E402
import docs_agent.tools.utils.html_docx_images as images_mod  # noqa: E402

_TINY_PNG_B64 = "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAYAAAAfFcSJAAAADUlEQVR42mP8z8BQDwAEhQGAhKmMIQAAAABJRU5ErkJggg=="
_TINY_PNG = base64.b64decode(_TINY_PNG_B64)


def test_relative_image_resolves_from_base_dir_after_chdir(tmp_path, monkeypatch):
    """Relative image src resolves from base_dir even when cwd differs (fix for preview vs export divergence)."""
    project_dir = tmp_path / "proj" / "documents"
    assets_dir = project_dir / "assets"
    assets_dir.mkdir(parents=True)
    (assets_dir / "inside.png").write_bytes(_TINY_PNG)

    # cwd != project_dir: direct _load_image_stream without base_dir would return None
    monkeypatch.chdir(tmp_path)

    # Without base_dir, relative lookup uses cwd and fails
    assert _load_image_stream("assets/inside.png") is None
    # With base_dir, it must succeed
    result = _load_image_stream("assets/inside.png", base_dir=project_dir)
    assert result is not None
    # result must be a seekable stream (python-docx requires .seek(0))
    import io
    assert isinstance(result, io.BytesIO)
    assert result.getvalue() == _TINY_PNG

    # Also verify html_to_docx respects base_dir after chdir (integration)
    html = '<html><body><p>hello</p><img src="assets/inside.png" alt="fallback"></body></html>'
    output_path = project_dir / "out.docx"
    # Mock table widths to avoid playwright
    with patch("docs_agent.tools.utils.html_docx_core._compute_table_auto_widths", return_value={}), \
         patch("docs_agent.tools.utils.html_docx_core._annotate_tables", side_effect=lambda s: str(s)):
        html_to_docx(html, output_path, base_dir=project_dir)
    assert output_path.exists()
    # Verify docx contains an image (inline_shapes)
    from docx import Document
    doc = Document(str(output_path))
    # At least one inline shape (the image) or paragraph with picture
    assert len(doc.inline_shapes) >= 1


def test_traversal_blocked(tmp_path):
    """../secret traversal must be blocked even if file exists outside base_dir."""
    project_dir = tmp_path / "workspace" / "documents"
    project_dir.mkdir(parents=True)
    (project_dir / "inside.png").write_bytes(_TINY_PNG)
    secret = tmp_path / "secret.png"
    secret.write_bytes(_TINY_PNG)

    # Traversal that resolves outside base_dir should return None
    result = _load_image_stream("../secret.png", base_dir=project_dir)
    assert result is None
    result2 = _load_image_stream("../../secret.png", base_dir=project_dir)
    assert result2 is None
    # Using nested traversal
    result3 = _load_image_stream("assets/../../secret.png", base_dir=project_dir)
    assert result3 is None
    # Ensure legitimate inside still works
    assert _load_image_stream("inside.png", base_dir=project_dir) is not None


def test_absolute_outside_blocked(tmp_path):
    """Absolute path outside base_dir must be blocked."""
    project_dir = tmp_path / "proj2" / "documents"
    project_dir.mkdir(parents=True)
    inside = project_dir / "inside.png"
    inside.write_bytes(_TINY_PNG)
    outside = tmp_path / "outside.png"
    outside.write_bytes(_TINY_PNG)

    # Absolute outside should be blocked
    result = _load_image_stream(str(outside.resolve()), base_dir=project_dir)
    assert result is None
    # Absolute inside should be allowed
    result_inside = _load_image_stream(str(inside.resolve()), base_dir=project_dir)
    assert result_inside is not None
    import io
    assert isinstance(result_inside, io.BytesIO)
    assert result_inside.getvalue() == _TINY_PNG


def test_http_size_cap(tmp_path):
    """HTTP fetch must be capped at 10 MB (header + chunked)."""
    project_dir = tmp_path / "proj3"
    project_dir.mkdir(parents=True)

    # Oversized via Content-Length header
    class FakeHeaders(dict):
        def get(self, key, default=None):
            return super().get(key, default)

    class FakeResponse:
        def __init__(self, payload, length=None, headers=None):
            self._payload = payload
            self._offset = 0
            self.headers = FakeHeaders()
            if length is not None:
                self.headers["Content-Length"] = str(length)
            else:
                self.headers["Content-Length"] = str(len(payload))
            if headers:
                self.headers.update(headers)

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, size=-1):
            if size is None or size < 0:
                size = len(self._payload) - self._offset
            chunk = self._payload[self._offset:self._offset+size]
            self._offset += len(chunk)
            return chunk

        def getheader(self, name, default=None):
            return self.headers.get(name, default)

    # Small valid payload should succeed
    small = b"\x89PNG\r\n\x1a\n" + b"A"*100
    with patch.object(images_mod, "urlopen", return_value=FakeResponse(small)):
        res = _load_image_stream("https://example.com/small.png", base_dir=project_dir)
        assert res is not None

    # Oversized Content-Length header -> blocked without reading body (should return None)
    oversized_length = _MAX_IMAGE_BYTES + 1
    with patch.object(images_mod, "urlopen", return_value=FakeResponse(b"tiny", length=oversized_length)) as mock_open:
        res = _load_image_stream("https://example.com/big.png", base_dir=project_dir)
        assert res is None

    # Chunked oversize without length (no Content-Length) -> should be capped during read
    big_payload = b"A" * (_MAX_IMAGE_BYTES + 1024)

    class NoLengthResponse:
        def __init__(self, payload):
            self._payload = payload
            self._offset = 0
            self.headers = FakeHeaders()  # no Content-Length

        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

        def read(self, size=-1):
            if size is None or size < 0:
                size = len(self._payload) - self._offset
            chunk = self._payload[self._offset:self._offset+size]
            self._offset += len(chunk)
            return chunk

        def getheader(self, name, default=None):
            return None

    with patch.object(images_mod, "urlopen", return_value=NoLengthResponse(big_payload)):
        res = _load_image_stream("https://example.com/big2.png", base_dir=project_dir)
        assert res is None

    # Exactly at limit should succeed? limit is 10MB, payload 10MB should pass ( > limit fails)
    at_limit = b"B" * _MAX_IMAGE_BYTES
    with patch.object(images_mod, "urlopen", return_value=FakeResponse(at_limit, length=_MAX_IMAGE_BYTES)):
        res = _load_image_stream("https://example.com/atlimit.png", base_dir=project_dir)
        assert res is not None
