from __future__ import annotations

from private_rag.ingestion import parser
from private_rag.ingestion.parser import parse_source


def test_pdf_fallback_filters_container_syntax_and_stream_data_from_chunks() -> None:
    pdf_bytes = (
        b"%PDF-1.5\n"
        b"7 0 obj\n"
        b"<< /Type /XObject /Subtype /Form /BBox [ 0 0 100 100 ]\n"
        b"/Filter /FlateDecode /FormType 1 /Length 15\n"
        b"/Matrix [ 1 0 0 1 0 0 ] /Resources 8 0 R >>\n"
        b"stream\n"
        b"x ZYoF ~ % a ` e+ !V #h^I+9 y ;  vu:**: Eg Y Vy eY * Y 9 > H9dQBL8\n"
        b"Ti J8bK#Ib #L!  P&i7 9-cBq\n"
        b"endstream\n"
        b"endobj\n"
        b"Abstract\n"
        b"This patent describes a UV curable adhesive composition for structural bonding.\n"
        b"What is claimed is:\n"
        b"1. A composition comprising epoxy acrylate resin and photoinitiator.\n"
    )

    parsed = parse_source("US11370944.pdf", "application/pdf", pdf_bytes)
    parsed_text = "\n".join(segment.text for segment in parsed.segments)

    assert "%PDF" not in parsed_text
    assert "endstream" not in parsed_text
    assert "ZYoF" not in parsed_text
    assert "Ti J8bK" not in parsed_text
    assert "/FlateDecode" not in parsed_text
    assert "Abstract" in parsed_text
    assert "claims" in parsed.metadata["patent_section_hints"]


def test_pdf_fallback_marks_binary_only_pdf_as_needs_ocr_without_chunks() -> None:
    pdf_bytes = (
        b"%PDF-1.5\n%\xe2\xe3\xcf\xd3\n"
        b"7 0 obj\n"
        b"<< /Type /XObject /Subtype /Form /BBox [ 0 0 100 100 ]\n"
        b"/Filter /FlateDecode /FormType 1 /Length 15\n"
        b"/Matrix [ 1 0 0 1 0 0 ] /Resources 8 0 R >>\n"
        b"stream\n"
        b"x\x9c\x03\x00\x00\x00\x00\x01\n"
        b"endstream\n"
        b"endobj\n"
    )

    parsed = parse_source("scanned.pdf", "application/pdf", pdf_bytes)

    assert parsed.ocr_required is True
    assert parsed.segments == []
    assert parsed.warnings[-1] == (
        "PDF has little extractable text and should be inspected with OCR/page images."
    )


def test_pdf_fallback_does_not_chunk_uncompressed_stream_text_without_real_parser() -> None:
    pdf_bytes = (
        b"%PDF-1.5\n"
        b"7 0 obj\n"
        b"<< /Type /Page /Length 120 >>\n"
        b"stream\n"
        b"BT /F1 12 Tf (This visible sentence is inside a PDF content stream.) Tj ET\n"
        b"endstream\n"
        b"endobj\n"
    )

    parsed = parse_source("paper.pdf", "application/pdf", pdf_bytes)

    assert parsed.ocr_required is True
    assert parsed.segments == []


def test_pdf_parser_chain_uses_pypdf_first_when_it_extracts_text(monkeypatch) -> None:
    monkeypatch.setattr(
        parser,
        "_extract_with_pypdf",
        lambda data: parser.PdfExtractionResult(
            text="Abstract\npypdf extracted this patent claim text successfully.",
            parser_name="pypdf",
            parser_version="test",
            parser_chain=["pypdf"],
            page_count=2,
        ),
    )
    monkeypatch.setattr(
        parser,
        "_extract_with_pymupdf",
        lambda data: parser.PdfExtractionResult(
            text="PyMuPDF should not be reached when pypdf extracts text.",
            parser_name="pymupdf",
            parser_version="test",
            parser_chain=["pypdf", "pymupdf"],
            page_count=3,
        ),
    )

    parsed = parse_source("paper.pdf", "application/pdf", b"%PDF")

    assert parsed.parser_name == "pypdf"
    assert parsed.parser_version == "test"
    assert parsed.page_count == 2
    assert parsed.warnings == [
        "PDF has little extractable text and should be inspected with OCR/page images."
    ]


def test_pdf_parser_chain_falls_through_to_pymupdf(monkeypatch) -> None:
    empty_pypdf = parser.PdfExtractionResult(
        text="",
        parser_name="pypdf",
        parser_version="test",
        parser_chain=["pypdf"],
    )
    pymupdf_result = parser.PdfExtractionResult(
        text="Abstract\nPyMuPDF extracted enough readable patent text for chunking claims and examples.",
        parser_name="pymupdf",
        parser_version="test",
        parser_chain=["pypdf", "pymupdf"],
        page_count=3,
    )
    monkeypatch.setattr(parser, "_extract_with_pypdf", lambda data: empty_pypdf)
    monkeypatch.setattr(parser, "_extract_with_pymupdf", lambda data: pymupdf_result)

    parsed = parse_source("paper.pdf", "application/pdf", b"%PDF")

    assert parsed.parser_name == "pymupdf"
    assert parsed.page_count == 3
    assert parsed.metadata["parser_chain"] == ["pypdf", "pymupdf"]


def test_pdf_parser_chain_falls_through_to_docling(monkeypatch) -> None:
    empty_pypdf = parser.PdfExtractionResult(
        text="",
        parser_name="pypdf",
        parser_version="test",
        parser_chain=["pypdf"],
    )
    empty_pymupdf = parser.PdfExtractionResult(
        text="",
        parser_name="pymupdf",
        parser_version="test",
        parser_chain=["pypdf", "pymupdf"],
    )
    docling_result = parser.PdfExtractionResult(
        text="Abstract\nDocling extracted enough readable patent text for chunking claims and examples.",
        parser_name="docling",
        parser_version="test",
        parser_chain=["pypdf", "pymupdf", "docling"],
        page_count=3,
    )
    monkeypatch.setattr(parser, "_extract_with_pypdf", lambda data: empty_pypdf)
    monkeypatch.setattr(parser, "_extract_with_pymupdf", lambda data: empty_pymupdf)
    monkeypatch.setattr(parser, "_extract_with_docling", lambda data: docling_result)

    parsed = parse_source("paper.pdf", "application/pdf", b"%PDF")

    assert parsed.parser_name == "docling"
    assert parsed.page_count == 3
    assert parsed.metadata["parser_chain"] == ["pypdf", "pymupdf", "docling"]
