from __future__ import annotations

import re
from pathlib import Path

from private_rag.ingestion.parser import parse_source

GOLDEN_CORPUS_DIR = Path("documents/golden_corpus")


def test_expected_golden_corpus_fixture_paths_exist() -> None:
    manifest = GOLDEN_CORPUS_DIR / "checks" / "expected_features.yaml"
    fixture_names = re.findall(r"fixture_name:\s*([^\n]+)", manifest.read_text())

    assert fixture_names
    for fixture_name in fixture_names:
        assert (GOLDEN_CORPUS_DIR / fixture_name.strip()).exists()


def test_golden_corpus_non_pdf_fixtures_parse_with_provenance() -> None:
    text = (GOLDEN_CORPUS_DIR / "text" / "materials-synthesis-procedure.txt").read_bytes()
    annotation = (GOLDEN_CORPUS_DIR / "text" / "materials-synthesis-annotation.ann").read_bytes()
    markdown = (GOLDEN_CORPUS_DIR / "markdown" / "dataset-readme.md").read_bytes()

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


def test_ocr_golden_corpus_fixtures_are_image_backed_with_text_layers() -> None:
    test_ocr = GOLDEN_CORPUS_DIR / "ocr" / "TestOCR.pdf"
    patent_ocr = GOLDEN_CORPUS_DIR / "ocr" / "US2764565.pdf"

    parsed_test_ocr = parse_source("TestOCR.pdf", "application/pdf", test_ocr.read_bytes())
    parsed_patent_ocr = parse_source("US2764565.pdf", "application/pdf", patent_ocr.read_bytes())

    assert parsed_test_ocr.ocr_required is False
    assert parsed_test_ocr.page_count == 1
    assert len(parsed_test_ocr.text.strip()) > 500
    assert parsed_test_ocr.metadata["page_images_available"] is True

    assert parsed_patent_ocr.ocr_required is False
    assert parsed_patent_ocr.page_count == 10
    assert parsed_patent_ocr.metadata["document_kind"] == "patent_pdf"
    assert "drawings" in parsed_patent_ocr.metadata["patent_section_hints"]
    assert len(parsed_patent_ocr.text.strip()) > 1000


def test_png_roundtrip_ocr_fixtures_have_no_text_layer_and_need_ocr() -> None:
    fixture_names = [
        "TestOCR_from_png.pdf",
        "US2764565_from_png.pdf",
        "chemistry-heavy-si_from_png.pdf",
        "patent-chemistry_from_png.pdf",
        "patent-ocr-stress_from_png.pdf",
    ]

    for fixture_name in fixture_names:
        fixture = GOLDEN_CORPUS_DIR / "ocr" / fixture_name
        parsed = parse_source(fixture_name, "application/pdf", fixture.read_bytes())

        assert parsed.ocr_required is True
        assert parsed.text.strip() == ""
        assert parsed.segments == []
        assert parsed.page_count is not None
        assert parsed.page_count >= 1
        assert parsed.metadata["page_images_available"] is True
        assert parsed.metadata["parser_chain"] == ["pypdf", "pymupdf", "needs_ocr_gate"]
        assert any("PDF pages appear image-only" in warning for warning in parsed.warnings)
