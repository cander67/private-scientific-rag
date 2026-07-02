from __future__ import annotations

from io import BytesIO
from pathlib import Path

import pytest

from private_rag.ingestion.parser import parse_source

INGESTION_FIXTURES_DIR = Path("tests/fixtures/ingestion")


def _image_pdf_with_text_layer(text: str) -> bytes:
    fitz = pytest.importorskip("fitz")
    source = fitz.open()
    source_page = source.new_page(width=612, height=792)
    source_page.insert_textbox((72, 72, 540, 300), text, fontsize=11)
    pixmap = source_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)

    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(page.rect, pixmap=pixmap)
    page.insert_textbox((72, 72, 540, 300), text, fontsize=11, color=(1, 1, 1))
    data = BytesIO()
    document.save(data)
    return data.getvalue()


def _image_only_pdf(text: str) -> bytes:
    fitz = pytest.importorskip("fitz")
    source = fitz.open()
    source_page = source.new_page(width=612, height=792)
    source_page.insert_textbox((72, 72, 540, 300), text, fontsize=11)
    pixmap = source_page.get_pixmap(matrix=fitz.Matrix(1.5, 1.5), alpha=False)

    document = fitz.open()
    page = document.new_page(width=612, height=792)
    page.insert_image(page.rect, pixmap=pixmap)
    data = BytesIO()
    document.save(data)
    return data.getvalue()


def test_committed_non_pdf_fixtures_parse_with_provenance() -> None:
    text = (INGESTION_FIXTURES_DIR / "materials-synthesis-procedure.txt").read_bytes()
    annotation = (INGESTION_FIXTURES_DIR / "materials-synthesis-annotation.ann").read_bytes()
    markdown = (INGESTION_FIXTURES_DIR / "dataset-readme.md").read_bytes()

    parsed_text = parse_source("materials-synthesis-procedure.txt", "text/plain", text)
    parsed_annotation = parse_source(
        "materials-synthesis-annotation.ann",
        "text/plain",
        annotation,
    )
    parsed_markdown = parse_source("dataset-readme.md", "text/markdown", markdown)

    assert parsed_text.metadata["line_provenance"] is True
    assert parsed_text.segments[0].line_start == 1
    assert parsed_annotation.metadata["annotation_format"] == "brat_standoff"
    assert parsed_annotation.metadata["paired_text_detection"] == "same_basename"
    assert parsed_markdown.metadata["line_provenance"] is True
    assert "Annotated Materials Syntheses Dataset" in parsed_markdown.sections


def test_image_backed_pdf_with_existing_text_layer_parses_without_ocr() -> None:
    text = (
        "Abstract\n"
        "This image-backed PDF includes a searchable text layer from a prior OCR pass. "
        "It mentions patent drawings, Figure 1, claims, and a chemistry procedure so the "
        "parser has enough native text to chunk without invoking the OCR-needed gate."
    )

    parsed = parse_source(
        "existing-ocr-layer.pdf", "application/pdf", _image_pdf_with_text_layer(text)
    )

    assert parsed.ocr_required is False
    assert parsed.page_count == 1
    assert "searchable text layer" in parsed.text
    assert parsed.metadata["page_images_available"] is True
    assert "drawings" in parsed.metadata["patent_section_hints"]


def test_image_only_pdf_has_no_text_layer_and_needs_ocr() -> None:
    text = (
        "Abstract\n"
        "This page is visible only as pixels after a PNG round trip. The parser should "
        "not silently OCR it during PRD3, but it should preserve page-image availability."
    )

    parsed = parse_source("roundtrip-from-png.pdf", "application/pdf", _image_only_pdf(text))

    assert parsed.ocr_required is True
    assert parsed.text.strip() == ""
    assert parsed.segments == []
    assert parsed.page_count == 1
    assert parsed.metadata["page_images_available"] is True
    assert parsed.metadata["parser_chain"] == ["pypdf", "pymupdf", "needs_ocr_gate"]
    assert any("PDF pages appear image-only" in warning for warning in parsed.warnings)
