"""Convert documents to different formats (PDF, Markdown, TXT)."""

from pathlib import Path
from typing import Literal

from agency_swarm.tools import BaseTool, ToolOutputText, tool_output_file_from_path
from pydantic import Field

# Base directory for all document files
from .utils.doc_file_utils import get_project_dir, next_docx_version, normalize_document_name

# Characters that PDF fonts commonly lack glyphs for.
# Includes both proper Unicode typographic chars and ASCII control-char
# corruptions that sometimes appear when the LLM emits smart-quote/dash
# codepoints that get truncated to their low byte during serialisation.
_UNICODE_TO_ASCII = str.maketrans({
    "\u2018": "'",    # '  left single quotation mark
    "\u2019": "'",    # '  right single quotation mark / apostrophe
    "\u201c": '"',    # "  left double quotation mark
    "\u201d": '"',    # "  right double quotation mark
    "\u2013": "-",    # –  en dash
    "\u2014": "--",   # —  em dash
    "\u2026": "...",  # …  horizontal ellipsis
    "\u00a0": " ",    # non-breaking space
    # Corrupted forms: low-byte of U+2019 / U+2013 stored as control chars
    "\x19":   "'",    # truncated U+2019 right-single-quote low byte
    "\x11":   "-",    # truncated U+2011/U+2013 dash low byte
    "\x18":   "'",    # truncated U+2018 left-single-quote low byte
    "\x1c":   '"',    # truncated U+201C left-double-quote low byte
    "\x1d":   '"',    # truncated U+201D right-double-quote low byte
    "\x14":   "--",   # truncated U+2014 em-dash low byte
})


def _normalize_unicode(html: str) -> str:
    return html.translate(_UNICODE_TO_ASCII)


def _load_weasyprint_html():
    try:
        from weasyprint import HTML
    except (ImportError, OSError) as exc:
        raise RuntimeError(
            "PDF export requires WeasyPrint and its native system libraries. "
            "Install the WeasyPrint platform dependencies, then retry PDF export. "
            f"Original error: {exc}"
        ) from exc
    return HTML


def _embed_local_images(html_content: str, project_dir: Path) -> str:
    from .utils.html_docx_images import embed_local_images

    return embed_local_images(html_content, project_dir)


def _auto_page_breaks(html_content: str) -> str:
    from .utils.html_docx_playwright import auto_page_breaks

    return auto_page_breaks(html_content)


class ConvertDocument(BaseTool):
    """
    Convert a document to different formats.
    
    Supported conversions:
    - HTML → PDF (high-quality, print-ready)
    - HTML → DOCX (Word document)
    - HTML → Markdown (for documentation)
    - HTML → TXT (plain text)
    
    The tool reads the .source.html file and converts it to the requested format.
    The original files are preserved - conversion creates a new file.
    
    Use this tool to:
    - Create PDF versions for sharing/printing
    - Export to Markdown for documentation sites
    - Generate plain text versions
    """
    
    project_name: str = Field(
        ...,
        description="Name of the project folder containing the document"
    )
    
    document_name: str = Field(
        ...,
        description="Name of the document to convert (without extension)"
    )
    
    output_format: Literal["pdf", "docx", "markdown", "txt"] = Field(
        ...,
        description="""Target format for conversion:
- 'pdf': High-quality PDF (requires weasyprint)
- 'docx': Word document
- 'markdown': Markdown format (useful for documentation)
- 'txt': Plain text (strips all formatting)"""
    )
    
    overwrite: bool = Field(
        default=True,
        description="If True (default), overwrites existing converted file. If False, returns error if file exists."
    )

    def run(self):
        """Convert document to specified format."""
        try:
            project_dir = get_project_dir(self.project_name)

            if not project_dir.exists():
                return f"Error: Project '{self.project_name}' not found."

            doc_name = normalize_document_name(self.document_name)
            source_path = project_dir / f"{doc_name}.source.html"

            if not source_path.exists():
                return f"Error: Document '{doc_name}' not found in project '{self.project_name}'."

            # Determine output file extension
            ext_map = {
                "pdf": ".pdf",
                "docx": ".docx",
                "markdown": ".md",
                "txt": ".txt",
            }
            output_path = project_dir / f"{doc_name}{ext_map[self.output_format]}"

            # DOCX auto-versions; all other formats respect overwrite flag
            if self.output_format == "docx":
                output_path = next_docx_version(output_path)
            elif output_path.exists() and not self.overwrite:
                return (
                    f"Error: Output file '{output_path.name}' already exists. "
                    "Set overwrite=True to replace it."
                )

            html_content = source_path.read_text(encoding="utf-8")
            if self.output_format in ("pdf", "docx"):
                html_content = _embed_local_images(html_content, project_dir)
                html_content = _auto_page_breaks(html_content)

            if self.output_format == "pdf":
                self._convert_to_pdf(html_content, output_path)
            elif self.output_format == "docx":
                self._convert_to_docx(html_content, output_path)
            elif self.output_format == "markdown":
                self._convert_to_markdown(html_content, output_path)
            elif self.output_format == "txt":
                self._convert_to_txt(html_content, output_path)

            if not output_path.exists():
                return f"Error: Conversion failed to produce '{output_path.name}'."

            # For DOCX exports, save a snapshot of the HTML source alongside the file.
            # This is the version history — RestoreDocument can roll back to any snapshot.
            if self.output_format == "docx":
                snapshot_path = output_path.parent / f"{output_path.name}.snapshot.html"
                snapshot_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")

            output_size = output_path.stat().st_size

            message = f"""Successfully converted document to {self.output_format.upper()}!

Project: {self.project_name}
Document: {doc_name}
Source: {source_path.name}
Output: {output_path.name} ({output_size:,} bytes)

Path: {output_path}"""

            if self.output_format == "pdf":
                return [
                    ToolOutputText(text=message),
                    tool_output_file_from_path(output_path),
                ]

            return message
        except Exception as e:
            return f"Error converting document: {str(e)}"
    
    def _convert_to_pdf(self, html_content: str, output_path: Path):
        """Convert HTML to PDF using weasyprint."""
        HTML = _load_weasyprint_html()
        HTML(string=_normalize_unicode(html_content)).write_pdf(output_path)

    def _convert_to_docx(self, html_content: str, output_path: Path):
        """Convert HTML to DOCX using the internal converter."""
        from .utils.html_docx_core import html_to_docx

        html_to_docx(html_content, output_path)
    
    def _convert_to_markdown(self, html_content: str, output_path: Path):
        """Convert HTML to Markdown."""
        import html2text

        converter = html2text.HTML2Text()
        converter.body_width = 0  # Don't wrap text
        markdown = converter.handle(html_content)
        output_path.write_text(markdown, encoding="utf-8")
    
    def _convert_to_txt(self, html_content: str, output_path: Path):
        """Convert HTML to plain text."""
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(html_content, "html.parser")
        text = soup.get_text(separator="\n", strip=True)
        output_path.write_text(text, encoding="utf-8")


if __name__ == "__main__":
    from .CreateDocument import CreateDocument

    print("=" * 70)
    print("TEST: ConvertDocument Tool")
    print("=" * 70)
    print()
    
    print("Setup: Creating test document...")
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Sample Report</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        h1 { color: #0066cc; }
        h2 { color: #333; border-bottom: 2px solid #0066cc; padding-bottom: 5px; }
        p { line-height: 1.6; }
        table { border-collapse: collapse; width: 100%; margin: 20px 0; }
        th { background: #0066cc; color: white; padding: 10px; text-align: left; }
        td { border: 1px solid #ddd; padding: 8px; }
    </style>
</head>
<body>
    <h1>Annual Report 2026</h1>
    
    <h2>Executive Summary</h2>
    <p>
        This report provides an overview of our company's performance in 2026.
        We achieved significant growth across all key metrics.
    </p>
    
    <h2>Financial Highlights</h2>
    <table>
        <tr>
            <th>Metric</th>
            <th>2025</th>
            <th>2026</th>
            <th>Growth</th>
        </tr>
        <tr>
            <td>Revenue</td>
            <td>$10M</td>
            <td>$15M</td>
            <td>+50%</td>
        </tr>
        <tr>
            <td>Customers</td>
            <td>500</td>
            <td>800</td>
            <td>+60%</td>
        </tr>
    </table>
    
    <h2>Key Achievements</h2>
    <ul>
        <li>Launched new product line</li>
        <li>Expanded to 3 new markets</li>
        <li>Achieved profitability</li>
    </ul>
</body>
</html>"""
    
    create_tool = CreateDocument(
        project_name="test_convert",
        document_name="annual_report",
        content={"type": "html", "value": html_content},
        overwrite=True,
    )
    print(create_tool.run())
    print()
    
    # Test 1: Convert to PDF
    print("Test 1: Converting to PDF...")
    tool = ConvertDocument(
        project_name="test_convert",
        document_name="annual_report",
        output_format="pdf"
    )
    result = tool.run()
    print(result)
    print()
    
    # Test 2: Convert to Markdown
    print("Test 2: Converting to Markdown...")
    tool = ConvertDocument(
        project_name="test_convert",
        document_name="annual_report",
        output_format="markdown"
    )
    result = tool.run()
    print(result)
    print()
    
    # Test 3: Convert to TXT
    print("Test 3: Converting to plain text...")
    tool = ConvertDocument(
        project_name="test_convert",
        document_name="annual_report",
        output_format="txt"
    )
    result = tool.run()
    print(result)
    print()
    
    # Test 4: View markdown output
    if "✅" in result:
        print("Test 4: Viewing converted Markdown content...")
        from pathlib import Path
        md_path = get_project_dir("test_convert") / "annual_report.md"
        if md_path.exists():
            print("Markdown content:")
            print("-" * 70)
            print(md_path.read_text(encoding='utf-8')[:500])
            print("...")
            print("-" * 70)
    print()
    
    # Test 5: Convert non-existent document (should fail)
    print("Test 5: Attempting to convert non-existent document...")
    tool = ConvertDocument(
        project_name="test_convert",
        document_name="nonexistent",
        output_format="pdf"
    )
    print(tool.run())
    print()
    
    print("=" * 70)
    print("✅ ALL TESTS COMPLETE")
    print("=" * 70)
    print("\nNote: Some conversion tests may show warnings if optional dependencies")
    print("(weasyprint, html2text) are not installed. This is expected.")
