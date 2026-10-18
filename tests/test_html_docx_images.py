import base64
import sys
from pathlib import Path
from types import ModuleType


ROOT = Path(__file__).resolve().parents[1]


def _stub_svg2png(**_):
    return b""


cairosvg = ModuleType("cairosvg")
cairosvg.svg2png = _stub_svg2png
sys.modules["cairosvg"] = cairosvg
for package_name, package_path in (
    ("docs_agent", ROOT / "docs_agent"),
    ("docs_agent.tools", ROOT / "docs_agent" / "tools"),
    ("docs_agent.tools.utils", ROOT / "docs_agent" / "tools" / "utils"),
):
    package = ModuleType(package_name)
    package.__path__ = [str(package_path)]
    sys.modules[package_name] = package

from docs_agent.tools.utils.html_docx_images import embed_local_images  # noqa: E402


def test_embed_local_images_stays_within_base_dir(tmp_path):
    base_dir = tmp_path / "workspace" / "documents"
    base_dir.mkdir(parents=True)
    inside_bytes = b"inside image"
    secret_bytes = b"secret image"
    (base_dir / "inside.png").write_bytes(inside_bytes)
    (tmp_path / "secret.png").write_bytes(secret_bytes)

    html = '<img src="inside.png"><img src="../../secret.png">'

    result = embed_local_images(html, base_dir)

    inside_data = base64.b64encode(inside_bytes).decode("ascii")
    secret_data = base64.b64encode(secret_bytes).decode("ascii")
    assert f'src="data:image/png;base64,{inside_data}"' in result
    assert 'src="../../secret.png"' in result
    assert secret_data not in result
