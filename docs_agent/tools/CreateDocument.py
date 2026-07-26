"""Create a new document from HTML or Markdown content."""

from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Literal, Union

from agency_swarm.tools import BaseTool, ToolOutputText, tool_output_image_from_path
from playwright.sync_api import sync_playwright
from pydantic import BaseModel, Field
from .utils.html_validation import build_unsupported_error, find_unsupported_html
from .utils.html_docx_playwright import _launch_chromium_with_install
from .utils.html_docx_constants import _UA_RESET_STYLE
from .utils.doc_file_utils import get_project_dir, normalize_document_name
from .utils.html_docx_images import embed_local_images


class HtmlContent(BaseModel):
    type: Literal["html"]
    value: str


class MarkdownContent(BaseModel):
    type: Literal["markdown"]
    value: str


ContentInput = Union[HtmlContent, MarkdownContent]


class CreateDocument(BaseTool):
    """
    Create a new document from HTML or Markdown content.
    
    HTML workflow creates:
    - .source.html file (the canonical source of truth)

    Markdown workflow creates:
    - .md file only (no .docx or .pdf generation)
    
    HTML is used as the source format because it provides:
    - Full styling control (fonts, colors, spacing, etc.)
    - Standard conversion tools (weasyprint)
    - WYSIWYG editing experience
    - Easy web preview capability
    
    Use this tool to create new documents with custom formatting and styling.
    """
    
    project_name: str = Field(
        ...,
        description="Name of the project folder (creates/uses ./mnt/{project_name}/documents/). Use lowercase with underscores (e.g., 'business_proposals', 'client_reports')"
    )
    
    document_name: str = Field(
        ...,
        description="Name of the document file without extension (e.g., 'quarterly_report', 'contract_template'). Extension will be added automatically."
    )
    
    content: ContentInput = Field(
        ...,
        description="""Content object for the document.
        
HTML example:
{
  "type": "html",
  "value": "<!DOCTYPE html>..."
}

Markdown example:
{
  "type": "markdown",
  "value": "# Title\\n\\n- Item"
}
        """
    )
    
    overwrite: bool = Field(
        default=False,
        description="If True, overwrites existing document. If False (default), returns an error if document already exists."
    )

    def run(self):
        """Create a new document from HTML or Markdown content."""
        try:
            project_dir = get_project_dir(self.project_name)
            project_dir.mkdir(parents=True, exist_ok=True)
            (project_dir / "assets").mkdir(exist_ok=True)

            # Strip extension if the caller included one
            doc_name = normalize_document_name(self.document_name)

            content_value = self.content.value
            if not content_value:
                return "Error: content.value is required."

            if self.content.type == "markdown":
                return self._create_markdown(doc_name, project_dir, content_value)
            
            source_path = project_dir / f"{doc_name}.source.html"
            
            if source_path.exists() and not self.overwrite:
                return f"Error: Document '{doc_name}' already exists in project '{self.project_name}'. Use overwrite=True to replace it, or choose a different document name."
            
            normalized_html = _ensure_ua_reset(content_value)
            issues = find_unsupported_html(normalized_html)
            if issues:
                return build_unsupported_error(issues)
            source_path.write_text(normalized_html, encoding='utf-8')
            
            source_size = source_path.stat().st_size
            
            operation = "updated" if self.overwrite and source_path.exists() else "created"
            
            message = f"""Successfully {operation} document

Project: {self.project_name}
Document: {doc_name}

Files created:
  - {source_path.name} ({source_size:,} bytes)

Path: {source_path}

Note: The .source.html file is the canonical source to be used for document conversion."""
            try:
                preview = _build_html_preview_image(normalized_html, project_dir)
            except Exception:
                return ToolOutputText(text=message)

            return [
                ToolOutputText(text=message),
                preview,
            ]
            
        except Exception as e:
            return f"Error creating document: {str(e)}"

    def _create_markdown(self, doc_name, project_dir, markdown_value):
        md_path = project_dir / f"{doc_name}.md"
        if md_path.exists() and not self.overwrite:
            return f"Error: Document '{doc_name}' already exists in project '{self.project_name}'. Use overwrite=True to replace it, or choose a different document name."

        md_path.write_text(markdown_value, encoding="utf-8")
        if not md_path.exists():
            return f"Error: Markdown generation failed for document '{doc_name}'."
        md_size = md_path.stat().st_size
        operation = "updated" if self.overwrite and md_path.exists() else "created"

        return f"""Successfully {operation} document!

Project: {self.project_name}
Document: {doc_name}

Files created:
  - {md_path.name} ({md_size:,} bytes) [Markdown source]

Path: {md_path}

Note: Markdown workflow only creates a .md file and does not generate .docx or .pdf files."""

def _build_html_preview_image(html_content: str, base_dir: Path):
    """Render a preview JPEG of the HTML document.

    The temp file is written inside base_dir so Playwright resolves
    relative image paths correctly (mirrors the slides-agent pattern).
    Images are also embedded as data URIs for full fidelity.
    """
    import tempfile

    from PIL import Image

    preview_html = embed_local_images(html_content, base_dir)

    with tempfile.NamedTemporaryFile(
        mode="w",
        suffix=".html",
        delete=False,
        encoding="utf-8",
        dir=base_dir,
    ) as tmp_html:
        tmp_html.write(preview_html)
        tmp_html_path = Path(tmp_html.name)

    try:
        with TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            raw_jpg = tmp_dir_path / "preview_raw.jpg"
            out_jpg = tmp_dir_path / "preview.jpg"

            with sync_playwright() as p:
                browser = _launch_chromium_with_install(p)
                page = browser.new_page(viewport={"width": 794, "height": 1123})
                page.goto(tmp_html_path.as_uri())
                page.wait_for_load_state("networkidle")
                page.screenshot(path=str(raw_jpg), full_page=True, type="jpeg", quality=80)
                browser.close()

            img = Image.open(raw_jpg)
            new_size = (int(img.width * 0.75), int(img.height * 0.75))
            img = img.resize(new_size, Image.Resampling.LANCZOS)
            img.save(out_jpg, "JPEG", quality=75, optimize=True)

            return tool_output_image_from_path(out_jpg, detail="auto")
    finally:
        tmp_html_path.unlink(missing_ok=True)

def _ensure_ua_reset(html_content: str) -> str:
    """Ensure a UA reset style exists in the HTML head."""
    if "UA reset to neutralize browser defaults" in html_content:
        return html_content

    lower = html_content.lower()
    head_index = lower.find("<head")
    if head_index != -1:
        head_close = lower.find(">", head_index)
        if head_close != -1:
            return (
                html_content[: head_close + 1]
                + _UA_RESET_STYLE
                + html_content[head_close + 1 :]
            )

    if "<html" in lower:
        return html_content.replace("<html>", f"<html><head>{_UA_RESET_STYLE}</head>", 1)

    return f"<!DOCTYPE html><html><head>{_UA_RESET_STYLE}</head><body>{html_content}</body></html>"

if __name__ == "__main__":
    print("=" * 70)
    print("TEST: CreateDocument Tool")
    print("=" * 70)
    print()    
    html_simple = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Business Proposal</title>
</head>
<body>
    <h1 style="color: #0066cc; font-family: Arial, sans-serif;">Business Proposal</h1>
    
    <h2 style="color: #333; font-family: Arial, sans-serif;">Executive Summary</h2>
    <p style="font-family: Georgia, serif; font-size: 11pt; line-height: 1.5;">
        This proposal outlines our comprehensive approach to solving your business challenges.
        We bring extensive experience and proven methodologies to deliver results.
    </p>
    
    <h2 style="color: #333; font-family: Arial, sans-serif;">Our Services</h2>
    <ul style="font-family: Georgia, serif; font-size: 11pt; line-height: 1.5;">
        <li><strong>Consulting:</strong> Strategic business advisory</li>
        <li><strong>Implementation:</strong> End-to-end project execution</li>
        <li><strong>Support:</strong> Ongoing maintenance and optimization</li>
    </ul>
    
    <h2 style="color: #333; font-family: Arial, sans-serif;">Pricing</h2>
    <table style="width: 100%; border-collapse: collapse; font-family: Arial, sans-serif; font-size: 10pt;">
        <tr style="background: #0066cc; color: white;">
            <th style="padding: 10px; border: 1px solid #ccc; text-align: left;">Package</th>
            <th style="padding: 10px; border: 1px solid #ccc; text-align: right;">Price</th>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #ccc;">Basic</td>
            <td style="padding: 8px; border: 1px solid #ccc; text-align: right;">$5,000</td>
        </tr>
        <tr style="background: #f9f9f9;">
            <td style="padding: 8px; border: 1px solid #ccc;">Professional</td>
            <td style="padding: 8px; border: 1px solid #ccc; text-align: right;">$10,000</td>
        </tr>
        <tr>
            <td style="padding: 8px; border: 1px solid #ccc;">Enterprise</td>
            <td style="padding: 8px; border: 1px solid #ccc; text-align: right;">$25,000</td>
        </tr>
    </table>
</body>
</html>"""
    
    tool = CreateDocument(
        project_name="test_project",
        document_name="business_proposal",
        content={"type": "html", "value": html_simple},
    )
    print(tool.run())
    print()
