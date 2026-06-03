"""Convert HTML slides to an editable PowerPoint presentation via dom-to-pptx."""

import os
import subprocess
import tempfile
from pathlib import Path
from typing import List, Optional

from agency_swarm.tools import BaseTool
from pydantic import Field

from run_utils import _openswarm_product_roots
from .slide_file_utils import get_project_dir, next_pptx_version

RUNNER_JS = Path(__file__).parent / "html2pptx_runner.js"


class BuildPptxFromHtmlSlides(BaseTool):
    """
    Convert HTML slides to a fully editable PowerPoint presentation.

    Uses dom-to-pptx (via Playwright) to measure every element's exact computed
    position and style, then maps them to native PPTX shapes and text boxes.
    CSS gradients are converted to vector SVGs, inline SVGs are kept as editable
    vectors, custom fonts are auto-embedded, and text remains fully editable.

    The output file is auto-versioned: if my_deck.pptx already exists the tool
    saves my_deck_v2.pptx, then my_deck_v3.pptx, etc. Previous exports and their
    snapshots are never overwritten.

    Requires: Node.js with local node_modules (dom-to-pptx, playwright)
    """

    project_name: str = Field(
        ...,
        description="Presentation project folder name (e.g. 'my_pitch')",
    )
    slide_names: List[str] = Field(
        ...,
        description=(
            "Ordered list of slide names to include, e.g. ['slide_01', 'slide_02']. "
            "Use bare names (without .html) or include the extension — both work."
        ),
    )
    output_filename: str = Field(
        ...,
        description=(
            "Output filename stem, e.g. 'my_deck' (saved as my_deck.pptx inside "
            "the project folder). Including the .pptx extension is also accepted."
        ),
    )
    layout: str = Field(
        default="LAYOUT_16x9_1280",
        description=(
            "Presentation layout: LAYOUT_16x9_1280 (1280x720 HTML), "
            "LAYOUT_16x9_1920 (1920x1080 HTML), LAYOUT_16x9, LAYOUT_4x3, or LAYOUT_16x10"
        ),
    )
    tmp_dir: Optional[str] = Field(
        default=None,
        description="Optional temporary directory for intermediate files",
    )

    def run(self) -> str:
        """Convert HTML slides to PPTX."""
        project_dir = get_project_dir(self.project_name)

        html_paths = self._resolve_slide_paths(self.slide_names, project_dir)
        if isinstance(html_paths, str):
            return html_paths  # error message

        if not html_paths:
            return "Error: No slide names provided"

        valid_layouts = ["LAYOUT_16x9_1280", "LAYOUT_16x9_1920", "LAYOUT_16x9", "LAYOUT_4x3", "LAYOUT_16x10"]
        if self.layout not in valid_layouts:
            return f"Error: Invalid layout '{self.layout}'. Must be one of: {', '.join(valid_layouts)}"

        output_path = next_pptx_version(self._resolve_output_path(self.output_filename, project_dir))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        if not self._check_node():
            return "Error: Node.js not found. Please install Node.js."

        root = next(iter(_openswarm_product_roots()), Path(__file__).parent.parent.parent)
        node_modules = root / "node_modules"
        if not node_modules.exists():
            return (
                "Error: node_modules not found. Please run 'npm install' in the OpenSwarm product root.\n"
                f"Expected location: {node_modules}"
            )

        if not RUNNER_JS.exists():
            return f"Error: Runner script not found at {RUNNER_JS}"

        tmp_dir = self.tmp_dir or tempfile.mkdtemp(prefix="html2pptx_")

        cmd = [
            "node",
            str(RUNNER_JS),
            "--output", str(output_path),
            "--layout", self.layout,
            "--tmp-dir", tmp_dir,
            "--",
        ] + html_paths

        try:
            kwargs = {
                "capture_output": True,
                "text": True,
                "timeout": 300,
                "cwd": str(root),
                "env": {**os.environ, "OPENSWARM_PRODUCT_ROOT": str(root)},
            }
            if os.name == "nt":
                kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW

            result = subprocess.run(cmd, **kwargs)

            if result.returncode != 0:
                error_msg = result.stderr.strip() or result.stdout.strip()
                return f"Error converting HTML to PPTX:\n{error_msg}"

            self._write_snapshots(html_paths, output_path)
            snapshot_dir = output_path.parent / f"{output_path.name}.slides"
            return (
                f"Presentation saved to: {output_path}\n"
                f"Snapshot saved to: {snapshot_dir}\n"
                f"Converted {len(html_paths)} slide(s)"
            )

        except subprocess.TimeoutExpired:
            return "Error: Conversion timed out after 5 minutes"
        except Exception as e:
            return f"Error running html2pptx: {e}"

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _resolve_slide_paths(self, slide_names: List[str], project_dir: Path) -> list[str] | str:
        """Resolve slide name strings to absolute .html paths."""
        paths = []
        for name in slide_names:
            path = project_dir / (name if name.endswith(".html") else f"{name}.html")
            if not path.exists():
                return f"Error: Slide not found: {name} (looked for {path})"
            paths.append(str(path.absolute()))
        return paths

    def _resolve_output_path(self, output_filename: str, project_dir: Path) -> Path:
        """Return the full output .pptx path from a stem or filename."""
        stem = Path(output_filename).stem
        return project_dir / f"{stem}.pptx"

    def _write_snapshots(self, html_paths: list[str], output_pptx: Path) -> None:
        """Write self-contained HTML snapshots to <output>.pptx.slides/1.html, 2.html, …"""
        slides_dir = output_pptx.parent / f"{output_pptx.name}.slides"
        slides_dir.mkdir(parents=True, exist_ok=True)

        for i, html_path in enumerate(html_paths, start=1):
            src = Path(html_path)
            html = src.read_text(encoding="utf-8")
            html = self._inline_theme_css(html, src.parent)
            (slides_dir / f"{i}.html").write_text(html, encoding="utf-8")

    def _inline_theme_css(self, html: str, slide_dir: Path) -> str:
        """Inline local <link rel="stylesheet"> tags into sentinel-marked <style> blocks.

        External URLs (http/https/protocol-relative) are left as-is.
        Local files are inlined as:
            <!-- css-snapshot:<filename>:start -->
            <style>…</style>
            <!-- css-snapshot:<filename>:end -->
        so that RestoreSnapshot can reverse the operation exactly.
        """
        import re

        def replace_link(match: re.Match) -> str:
            href = match.group(1)
            if href.startswith(("http://", "https://", "//")):
                return match.group(0)
            css_path = (slide_dir / href).resolve()
            if not css_path.exists():
                return match.group(0)
            filename = css_path.name
            css = css_path.read_text(encoding="utf-8")
            return (
                f"<!-- css-snapshot:{filename}:start -->\n"
                f"<style>\n{css}\n</style>\n"
                f"<!-- css-snapshot:{filename}:end -->"
            )

        return re.sub(
            r'<link\b[^>]*\brel=["\']stylesheet["\'][^>]*\bhref=["\']([^"\']+)["\'][^>]*>',
            replace_link,
            html,
            flags=re.IGNORECASE,
        )

    def _check_node(self) -> bool:
        """Check if Node.js is available."""
        try:
            kwargs = {
                "capture_output": True,
                "timeout": 5,
                "text": True,
            }
            if os.name == "nt":
                kwargs["creationflags"] = 0x08000000  # CREATE_NO_WINDOW
            subprocess.run(["node", "--version"], **kwargs)
            return True
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False


if __name__ == "__main__":
    tool = BuildPptxFromHtmlSlides(
        project_name="dinosaur_presentation_v2",
        slide_names=["slide_01", "slide_02", "slide_03", "slide_04", "slide_05"],
        output_filename="dinosaur_presentation_v2",
        layout="LAYOUT_16x9_1280",
    )
    print(tool.run())
