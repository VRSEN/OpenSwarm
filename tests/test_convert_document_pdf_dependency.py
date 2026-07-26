import builtins

import docs_agent.tools.ConvertDocument as convert_module
from docs_agent.tools.ConvertDocument import ConvertDocument
from docs_agent.tools.RestoreDocument import RestoreDocument
from docs_agent.tools.utils.doc_file_utils import (
    get_project_dir,
    normalize_document_name,
    normalize_docx_filename,
)


def test_convert_document_import_does_not_require_weasyprint():
    assert ConvertDocument.__name__ == "ConvertDocument"


def test_pdf_conversion_reports_missing_weasyprint_native_dependency(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project" / "documents"
    project_dir.mkdir(parents=True)
    (project_dir / "report.source.html").write_text(
        "<!doctype html><html><body><h1>Report</h1></body></html>",
        encoding="utf-8",
    )

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise OSError("libpango-1.0-0: cannot open shared object file")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(convert_module, "get_project_dir", lambda _project_name: project_dir)
    monkeypatch.setattr(convert_module, "_embed_local_images", lambda html, _project_dir: html)
    monkeypatch.setattr(convert_module, "_auto_page_breaks", lambda html: html)

    result = ConvertDocument(
        project_name="demo_project",
        document_name="report",
        output_format="pdf",
    ).run()

    assert "PDF export requires WeasyPrint" in result
    assert "libpango-1.0-0" in result
    assert not (project_dir / "report.pdf").exists()


def test_markdown_conversion_still_works_without_weasyprint(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project" / "documents"
    project_dir.mkdir(parents=True)
    (project_dir / "report.source.html").write_text(
        "<!doctype html><html><body><h1>Report</h1><p>Hello</p></body></html>",
        encoding="utf-8",
    )

    real_import = builtins.__import__

    def guarded_import(name, *args, **kwargs):
        if name == "weasyprint":
            raise OSError("libpango-1.0-0: cannot open shared object file")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    monkeypatch.setattr(convert_module, "get_project_dir", lambda _project_name: project_dir)
    def fail_if_embedding_runs(_html, _project_dir):
        raise AssertionError("Markdown conversion should not embed local images")

    monkeypatch.setattr(convert_module, "_embed_local_images", fail_if_embedding_runs)

    result = ConvertDocument(
        project_name="demo_project",
        document_name="report",
        output_format="markdown",
    ).run()

    assert "Successfully converted document to MARKDOWN" in result
    markdown = (project_dir / "report.md").read_text(encoding="utf-8")
    assert "# Report" in markdown
    assert "Hello" in markdown


def test_txt_conversion_skips_render_only_image_embedding(monkeypatch, tmp_path):
    project_dir = tmp_path / "demo_project" / "documents"
    project_dir.mkdir(parents=True)
    (project_dir / "report.source.html").write_text(
        "<!doctype html><html><body><h1>Report</h1><img src='assets/chart.png'><p>Hello</p></body></html>",
        encoding="utf-8",
    )

    def fail_if_embedding_runs(_html, _project_dir):
        raise AssertionError("TXT conversion should not embed local images")

    monkeypatch.setattr(convert_module, "get_project_dir", lambda _project_name: project_dir)
    monkeypatch.setattr(convert_module, "_embed_local_images", fail_if_embedding_runs)

    result = ConvertDocument(
        project_name="demo_project",
        document_name="report",
        output_format="txt",
    ).run()

    assert "Successfully converted document to TXT" in result
    text = (project_dir / "report.txt").read_text(encoding="utf-8")
    assert "Report" in text
    assert "Hello" in text


def test_document_path_components_reject_traversal():
    invalid_values = [
        "../escape",
        "nested/project",
        "nested\\project",
        "/tmp/project",
        ".",
        "..",
        "",
        "safe\x00name",
    ]

    for value in invalid_values:
        try:
            get_project_dir(value)
        except ValueError as exc:
            assert "project_name" in str(exc)
        else:
            raise AssertionError(f"project_name accepted unsafe value: {value!r}")

        try:
            normalize_document_name(value)
        except ValueError as exc:
            assert "document_name" in str(exc)
        else:
            raise AssertionError(f"document_name accepted unsafe value: {value!r}")

        try:
            normalize_docx_filename(value)
        except ValueError as exc:
            assert "docx_filename" in str(exc)
        else:
            raise AssertionError(f"docx_filename accepted unsafe value: {value!r}")


def test_document_name_normalization_keeps_single_safe_stem():
    assert normalize_document_name("report.source.html") == "report"
    assert normalize_document_name("report.html") == "report"
    assert normalize_document_name("report.docx") == "report"
    assert normalize_document_name("report.md") == "report"
    assert normalize_docx_filename("report") == "report.docx"
    assert normalize_docx_filename("report_v2.docx") == "report_v2.docx"


def test_invalid_restore_filename_returns_tool_error():
    result = RestoreDocument(project_name="safe_project", docx_filename="../report.docx").run()

    assert result.startswith("Error restoring document:")
    assert "docx_filename" in result
