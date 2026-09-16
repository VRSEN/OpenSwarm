from pathlib import Path
from typing import Optional

from bs4 import BeautifulSoup
from bs4.element import Comment, NavigableString, Tag
from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn
from docx.shared import Pt

from .html_docx_blocks import _handle_block
from .html_docx_page import (
    _apply_page_background,
    _apply_page_settings,
    _ensure_display_background_shape,
)
from .html_docx_playwright import _annotate_tables, _compute_table_auto_widths
from .html_docx_selectors import _compute_style_map, _extract_css_rules
from .html_docx_shared import _remove_trailing_empty_paragraph


def html_to_docx(html_content: str, output_path: Path, base_dir: Optional[Path] = None) -> None:
    if base_dir is None:
        base_dir = output_path.parent
    doc = Document()
    _set_default_paragraph_style(doc)
    _apply_page_settings(doc, html_content)
    _remove_trailing_empty_paragraph(doc)
    soup = BeautifulSoup(html_content, "html.parser")
    table_auto_widths = _compute_table_auto_widths(_annotate_tables(soup))
    css_rules = _extract_css_rules(soup)

    body = soup.body or soup
    body_style = _compute_style_map(body, css_rules)
    _apply_page_background(doc, body_style)
    _ensure_display_background_shape(doc)
    content_root = _unwrap_layout_table(body) or body
    for child in content_root.children:
        _handle_block(child, doc, css_rules, body_style, table_auto_widths, base_dir)

    # When the document body starts with a table, Word renders an implicit gap above it.
    # Inserting a 1pt-height anchor paragraph before the first table eliminates that gap.
    _insert_top_anchor_paragraph(doc)

    doc.save(str(output_path))


_SKIP_TAGS = {"style", "script", "head", "meta", "link", "title", "noscript"}


def _unwrap_layout_table(body: Tag) -> Optional[Tag]:
    """Return the single content cell of the outer centered layout table.

    Many generated docs wrap the entire body in a single-row, single-cell table
    purely to constrain width (`width:547pt; margin:auto`). In DOCX this turns
    the whole document into one giant table cell, which makes Word paginate
    nested content poorly. When we detect that specific wrapper, process the
    cell's children directly at the document body level instead.
    """
    content_children = [
        child
        for child in body.children
        if not isinstance(child, Comment)
        and not (isinstance(child, NavigableString) and not child.strip())
        and not (isinstance(child, Tag) and child.name in _SKIP_TAGS)
    ]
    if len(content_children) != 1:
        return None

    table = content_children[0]
    if not isinstance(table, Tag) or table.name != "table":
        return None
    if not _is_layout_wrapper_table(table):
        return None

    rows = _direct_rows(table)
    if len(rows) != 1:
        return None

    cells = rows[0].find_all(["td", "th"], recursive=False)
    if len(cells) != 1:
        return None

    return cells[0]


def _is_layout_wrapper_table(table: Tag) -> bool:
    style = (table.get("style") or "").replace(" ", "").lower()
    return (
        "width:547pt" in style
        and "margin-left:auto" in style
        and "margin-right:auto" in style
    )


def _direct_rows(table: Tag) -> list[Tag]:
    rows = table.find_all("tr", recursive=False)
    if rows:
        return rows

    rows = []
    for section in table.find_all(["thead", "tbody", "tfoot"], recursive=False):
        rows.extend(section.find_all("tr", recursive=False))
    return rows


def _insert_top_anchor_paragraph(doc: Document) -> None:
    """Insert a near-zero-height paragraph before the first body-level table."""
    body_el = doc._body._body
    first = body_el[0] if len(body_el) else None
    if first is None or first.tag != qn("w:tbl"):
        return

    p_el = OxmlElement("w:p")
    p_pr = OxmlElement("w:pPr")
    spacing = OxmlElement("w:spacing")
    spacing.set(qn("w:before"), "0")
    spacing.set(qn("w:after"), "0")
    spacing.set(qn("w:line"), "20")    # 1pt exact
    spacing.set(qn("w:lineRule"), "exact")
    ctx = OxmlElement("w:contextualSpacing")
    r_pr = OxmlElement("w:rPr")
    sz = OxmlElement("w:sz")
    sz.set(qn("w:val"), "2")           # 1pt font
    r_pr.append(sz)
    p_pr.append(spacing)
    p_pr.append(ctx)
    p_pr.append(r_pr)
    p_el.append(p_pr)
    body_el.insert(0, p_el)


def _set_default_paragraph_style(doc: Document) -> None:
    try:
        normal = doc.styles["Normal"]
    except KeyError:
        return
    normal_pf = normal.paragraph_format
    normal_pf.space_before = Pt(0)
    normal_pf.space_after = Pt(0)
