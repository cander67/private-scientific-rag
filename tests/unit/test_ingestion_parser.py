from __future__ import annotations

import pytest

from private_rag.ingestion import parser
from private_rag.ingestion.parser import ParserExecutionSettings, parse_source


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


def test_pdf_parser_records_scientific_structure_hints(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        parser,
        "_extract_with_pypdf",
        lambda data: parser.PdfExtractionResult(
            text=(
                "Abstract\n"
                "Figure 1 shows the device layout.\n"
                "Table 2 lists measured properties.\n"
                "Scheme 3 summarizes the synthesis."
            ),
            parser_name="pypdf",
            parser_version="test",
            parser_chain=["pypdf"],
            page_count=1,
        ),
    )

    parsed = parse_source("paper.pdf", "application/pdf", b"%PDF")

    assert parsed.metadata["structure_hints"] == ["tables", "figures", "captions"]


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


def test_pdf_parser_chain_uses_pypdf_first_when_it_extracts_text(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_pdf_parser_chain_falls_through_to_pymupdf(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_pdf_parser_chain_falls_through_to_docling(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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


def test_auto_parser_route_preserves_prd3_chain(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def empty_pypdf(data: bytes) -> parser.PdfExtractionResult:
        calls.append("pypdf")
        return parser.PdfExtractionResult(
            text="",
            parser_name="pypdf",
            parser_version="test",
            parser_chain=["pypdf"],
        )

    def text_pymupdf(data: bytes) -> parser.PdfExtractionResult:
        calls.append("pymupdf")
        return parser.PdfExtractionResult(
            text="Abstract\nPyMuPDF extracted enough text for the default auto route.",
            parser_name="pymupdf",
            parser_version="test",
            parser_chain=["pypdf", "pymupdf"],
            page_count=1,
        )

    monkeypatch.setattr(parser, "_extract_with_pypdf", empty_pypdf)
    monkeypatch.setattr(parser, "_extract_with_pymupdf", text_pymupdf)

    parsed = parse_source(
        "paper.pdf",
        "application/pdf",
        b"%PDF",
        parser_settings=ParserExecutionSettings(
            structured_parser="auto", fallback_parser="docling"
        ),
    )

    assert calls == ["pypdf", "pymupdf"]
    assert parsed.parser_name == "pymupdf"
    assert parsed.metadata["parser_route"] == ["pypdf", "pymupdf"]


def test_explicit_parser_route_uses_selected_parser_first(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls: list[str] = []

    def text_pypdf(data: bytes) -> parser.PdfExtractionResult:
        calls.append("pypdf")
        return parser.PdfExtractionResult(
            text="pypdf should not run before explicit PyMuPDF.",
            parser_name="pypdf",
            parser_version="test",
            parser_chain=["pypdf"],
        )

    def text_pymupdf(data: bytes) -> parser.PdfExtractionResult:
        calls.append("pymupdf")
        return parser.PdfExtractionResult(
            text="Abstract\nPyMuPDF was explicitly selected for this document.",
            parser_name="pymupdf",
            parser_version="test",
            parser_chain=["pymupdf"],
            page_count=2,
        )

    monkeypatch.setattr(parser, "_extract_with_pypdf", text_pypdf)
    monkeypatch.setattr(parser, "_extract_with_pymupdf", text_pymupdf)

    parsed = parse_source(
        "paper.pdf",
        "application/pdf",
        b"%PDF",
        parser_settings=ParserExecutionSettings(
            structured_parser="pymupdf",
            fallback_parser="pypdf",
        ),
    )

    assert calls == ["pymupdf"]
    assert parsed.parser_name == "pymupdf"
    assert parsed.metadata["parser_route"] == ["pymupdf"]
    assert parsed.metadata["parser_settings"] == {
        "structured_parser": "pymupdf",
        "fallback_parser": "pypdf",
    }


def test_explicit_parser_route_uses_configured_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        parser,
        "_extract_with_pymupdf",
        lambda data: parser.PdfExtractionResult(
            text="",
            parser_name="pymupdf",
            parser_version="test",
            parser_chain=["pymupdf"],
            warnings=["pymupdf did not recover text."],
        ),
    )
    monkeypatch.setattr(
        parser,
        "_extract_with_built_in_pdf_fallback",
        lambda data: parser.PdfExtractionResult(
            text="Abstract\nBuilt in fallback recovered enough metadata text.",
            parser_name=parser.BUILT_IN_PARSER_NAME,
            parser_version=parser.BUILT_IN_PARSER_VERSION,
            parser_chain=["built_in_fallback"],
        ),
    )

    parsed = parse_source(
        "paper.pdf",
        "application/pdf",
        b"%PDF",
        parser_settings=ParserExecutionSettings(
            structured_parser="pymupdf",
            fallback_parser="built_in_fallback",
        ),
    )

    assert parsed.parser_name == parser.BUILT_IN_PARSER_NAME
    assert parsed.metadata["parser_route"] == ["pymupdf", "built_in_fallback"]
    assert "pymupdf did not recover text." in parsed.warnings


def test_missing_optional_parser_dependency_warns_and_falls_back(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        parser,
        "_extract_with_docling",
        lambda data: parser.PdfExtractionResult(
            text="",
            parser_name="docling",
            parser_version="not-installed",
            parser_chain=["docling"],
            warnings=["docling unavailable or failed: ImportError"],
        ),
    )
    monkeypatch.setattr(
        parser,
        "_extract_with_pypdf",
        lambda data: parser.PdfExtractionResult(
            text="Abstract\npypdf recovered enough readable fallback text.",
            parser_name="pypdf",
            parser_version="test",
            parser_chain=["pypdf"],
            page_count=1,
        ),
    )

    parsed = parse_source(
        "paper.pdf",
        "application/pdf",
        b"%PDF",
        parser_settings=ParserExecutionSettings(
            structured_parser="docling",
            fallback_parser="pypdf",
        ),
    )

    assert parsed.parser_name == "pypdf"
    assert parsed.metadata["parser_route"] == ["docling", "pypdf"]
    assert "docling unavailable or failed: ImportError" in parsed.warnings
