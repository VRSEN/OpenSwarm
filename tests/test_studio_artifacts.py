"""Studio artifact listing."""

from pathlib import Path

from backend.services.studio_artifacts import get_mnt_root, list_artifacts, safe_mnt_path


def test_list_artifacts_empty(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.services.studio_artifacts.get_mnt_root", lambda: tmp_path)
    assert list_artifacts() == []


def test_list_and_resolve_artifact(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.services.studio_artifacts.get_mnt_root", lambda: tmp_path)
    doc = tmp_path / "my_project" / "documents" / "report.pdf"
    doc.parent.mkdir(parents=True)
    doc.write_bytes(b"%PDF-test")

    items = list_artifacts()
    assert len(items) == 1
    assert items[0]["name"] == "report.pdf"
    assert items[0]["category"] == "document"

    resolved = safe_mnt_path("my_project/documents/report.pdf")
    assert resolved == doc.resolve()
    assert items[0]["preview_type"] == "pdf"


def test_safe_mnt_path_rejects_traversal(tmp_path, monkeypatch):
    monkeypatch.setattr("backend.services.studio_artifacts.get_mnt_root", lambda: tmp_path)
    assert safe_mnt_path("../../etc/passwd") is None
