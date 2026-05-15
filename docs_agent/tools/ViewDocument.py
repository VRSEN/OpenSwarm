"""View document content from HTML source."""

from typing import Optional, List
from agency_swarm.tools import BaseTool
from pydantic import Field

from .utils.doc_file_utils import get_project_dir, normalize_document_name


class ViewDocument(BaseTool):
    """
    View the content of an existing document (reads from .source.html file).
    
    This tool reads the HTML source file which is the canonical source of truth.
    Optionally specify a line range to view only part of the document.
    
    Use this tool to:
    - Read existing document content before editing
    - Check document structure and formatting
    - Verify specific sections of a document
    """
    
    project_name: str = Field(
        ...,
        description="Name of the project folder containing the document"
    )
    
    document_name: str = Field(
        ...,
        description="Name of the document to view (without extension)"
    )
    
    view_range: Optional[List[int]] = Field(
        default=None,
        description="Optional line range [start_line, end_line] (1-based, inclusive). If not provided, shows entire document. Example: [1, 50] shows first 50 lines."
    )

    def run(self):
        """View document content."""
        try:
            project_dir = get_project_dir(self.project_name)

            if not project_dir.exists():
                return f"Error: Project '{self.project_name}' not found."

            doc_name = normalize_document_name(self.document_name)
            source_path = project_dir / f"{doc_name}.source.html"
            docx_path = project_dir / f"{doc_name}.docx"
            md_path = project_dir / f"{doc_name}.md"
            
            if not source_path.exists() and not md_path.exists():
                return f"Error: Document '{doc_name}' not found in project '{self.project_name}'."
            
            if source_path.exists():
                content = source_path.read_text(encoding="utf-8")
            else:
                content = md_path.read_text(encoding="utf-8")
            lines = content.split('\n')
            total_lines = len(lines)

            if self.view_range:
                if len(self.view_range) != 2:
                    return "❌ Error: view_range must be a list of exactly 2 integers [start_line, end_line]"

                start_line, end_line = self.view_range

                if start_line < 1 or end_line < start_line or start_line > total_lines:
                    return f"Error: Invalid line range [{start_line}, {end_line}]. Document has {total_lines} lines."

                start_idx = start_line - 1  # 1-based → 0-based
                end_idx = min(end_line, total_lines)
                
                selected_lines = lines[start_idx:end_idx]
                content_to_show = '\n'.join(selected_lines)
                
                range_info = f"Lines {start_line}-{end_idx} of {total_lines}"
            else:
                content_to_show = content
                range_info = f"All {total_lines} lines"
            
            source_size = source_path.stat().st_size if source_path.exists() else md_path.stat().st_size
            docx_exists = docx_path.exists()
            docx_info = (
                f"\n  - {docx_path.name} exists"
                if docx_exists
                else f"\n  - {docx_path.name} NOT FOUND (needs regeneration)"
            )
            
            return f"""# Document: {doc_name}
Project: {self.project_name}
Source: {(source_path.name if source_path.exists() else md_path.name)} ({source_size:,} bytes){docx_info}
Viewing: {range_info}

---

{content_to_show}"""
            
        except Exception as e:
            return f"Error viewing document: {str(e)}"


if __name__ == "__main__":
    print("=" * 70)
    print("TEST: ViewDocument Tool")
    print("=" * 70)
    print()
    
    # First, create a test document to view
    from CreateDocument import CreateDocument
    
    print("Setup: Creating test document...")
    html_content = """<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <title>Test Document</title>
</head>
<body>
    <h1>Test Document Title</h1>
    <p>This is line 1 of content.</p>
    <p>This is line 2 of content.</p>
    <p>This is line 3 of content.</p>
    <p>This is line 4 of content.</p>
    <p>This is line 5 of content.</p>
    <h2>Section 2</h2>
    <p>More content here in section 2.</p>
    <ul>
        <li>Item 1</li>
        <li>Item 2</li>
        <li>Item 3</li>
    </ul>
</body>
</html>"""
    
    create_tool = CreateDocument(
        project_name="test_view",
        document_name="sample_doc",
        content={"type": "html", "value": html_content},
        overwrite=True
    )
    print(create_tool.run())
    print()

    tool = ViewDocument(
        project_name="test_view",
        document_name="sample_doc",
        view_range=[1, 10]
    )
    print(tool.run())
