from __future__ import annotations

import re
from dataclasses import dataclass, field
from io import BytesIO
from pathlib import Path
from tempfile import NamedTemporaryFile
from typing import Any

from private_rag.ingestion.schemas import ParsedDocument, ParsedSegment, SourceType

BUILT_IN_PARSER_NAME = "private-rag-built-in"
BUILT_IN_PARSER_VERSION = "prd3-v1"
PDF_MIN_TEXT_LENGTH = 80

_PATENT_SECTION_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("abstract", re.compile(r"\babstract\b", re.IGNORECASE)),
    ("claims", re.compile(r"\b(claims?|what is claimed is)\b", re.IGNORECASE)),
    ("description", re.compile(r"\b(detailed description|description)\b", re.IGNORECASE)),
    ("examples", re.compile(r"\b(examples?|example\s+\d+)\b", re.IGNORECASE)),
    ("classifications", re.compile(r"\b(cpc|ipc|classification|c08|c09j)\b", re.IGNORECASE)),
    (
        "drawings",
        re.compile(r"\b(brief description of the drawings|fig\.|figure)\b", re.IGNORECASE),
    ),
)


def detect_source_type(filename: str, content_type: str | None) -> SourceType:
    suffix = Path(filename).suffix.lower()
    normalized_content_type = (content_type or "").lower()
    if suffix == ".pdf" or normalized_content_type == "application/pdf":
        return "pdf"
    if suffix == ".md" or suffix == ".markdown" or "markdown" in normalized_content_type:
        return "markdown"
    if suffix == ".ann":
        return "annotation"
    return "text"


def parse_source(filename: str, content_type: str | None, data: bytes) -> ParsedDocument:
    source_type = detect_source_type(filename, content_type)
    if source_type == "pdf":
        return _parse_pdf(data)
    if source_type == "markdown":
        return _parse_markdown(data)
    if source_type == "annotation":
        return _parse_annotation(data)
    return _parse_text(data)


def _parse_pdf(data: bytes) -> ParsedDocument:
    result = _extract_pdf_with_parser_chain(data)
    text = result.text
    page_count = max(1, len(re.findall(rb"/Type\s*/Page\b", data)))
    if result.page_count is not None:
        page_count = result.page_count
    warnings: list[str] = [*result.warnings]
    ocr_required = False
    if len(text.strip()) < PDF_MIN_TEXT_LENGTH:
        ocr_required = True
        warnings.append(
            "PDF has little extractable text and should be inspected with OCR/page images."
        )

    segments = result.segments or _segments_from_lines(text, page_count=page_count)
    sections = _unique_sections(segments)
    patent_sections = _detect_patent_sections(text)
    structure_hints = _detect_scientific_structure_hints(text)
    metadata: dict[str, object] = {
        "page_images_available": True,
        "patent_section_hints": patent_sections,
        "parser_chain": result.parser_chain,
        "structure_hints": structure_hints,
    }
    if patent_sections:
        metadata["document_kind"] = "patent_pdf"

    return ParsedDocument(
        source_type="pdf",
        text=text,
        parser_name=result.parser_name,
        parser_version=result.parser_version,
        segments=segments,
        page_count=page_count,
        line_count=len(text.splitlines()),
        sections=sections,
        warnings=warnings,
        ocr_required=ocr_required,
        metadata=metadata,
    )


def _parse_markdown(data: bytes) -> ParsedDocument:
    text = _decode(data)
    segments = _segments_from_markdown(text)
    return ParsedDocument(
        source_type="markdown",
        text=text,
        parser_name=BUILT_IN_PARSER_NAME,
        parser_version=BUILT_IN_PARSER_VERSION,
        segments=segments,
        line_count=len(text.splitlines()),
        sections=_unique_sections(segments),
        metadata={"line_provenance": True},
    )


def _parse_annotation(data: bytes) -> ParsedDocument:
    text = _decode(data)
    line_records = _line_records(text)
    segments = [
        ParsedSegment(
            text=stripped,
            section="annotations",
            line_start=index,
            line_end=index,
            char_start=char_start,
            char_end=char_end,
            metadata={"annotation_format": "brat_standoff"},
        )
        for index, stripped, char_start, char_end in line_records
        if stripped
    ]
    return ParsedDocument(
        source_type="annotation",
        text=text,
        parser_name=BUILT_IN_PARSER_NAME,
        parser_version=BUILT_IN_PARSER_VERSION,
        segments=segments,
        line_count=len(line_records),
        sections=["annotations"] if segments else [],
        metadata={
            "annotation_format": "brat_standoff",
            "paired_text_detection": "same_basename",
        },
    )


def _parse_text(data: bytes) -> ParsedDocument:
    text = _decode(data)
    segments = _segments_from_lines(text, page_count=None)
    return ParsedDocument(
        source_type="text",
        text=text,
        parser_name=BUILT_IN_PARSER_NAME,
        parser_version=BUILT_IN_PARSER_VERSION,
        segments=segments,
        line_count=len(text.splitlines()),
        sections=_unique_sections(segments),
        metadata={"line_provenance": True},
    )


@dataclass
class PdfExtractionResult:
    text: str
    parser_name: str
    parser_version: str
    parser_chain: list[str]
    page_count: int | None = None
    segments: list[ParsedSegment] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _extract_pdf_with_parser_chain(data: bytes) -> PdfExtractionResult:
    failures: list[str] = []
    pypdf_result = _extract_with_pypdf(data)
    if pypdf_result.text.strip():
        return pypdf_result
    failures.extend(pypdf_result.warnings)

    pymupdf_result = _extract_with_pymupdf(data)
    if pymupdf_result.text.strip():
        return pymupdf_result
    failures.extend(pymupdf_result.warnings)

    if _has_image_pages_without_native_text(data):
        return PdfExtractionResult(
            text="",
            parser_name=BUILT_IN_PARSER_NAME,
            parser_version=BUILT_IN_PARSER_VERSION,
            parser_chain=["pypdf", "pymupdf", "needs_ocr_gate"],
            page_count=pymupdf_result.page_count,
            warnings=[
                *failures,
                "PDF pages appear image-only; OCR is required before text chunking.",
            ],
        )

    docling_result = _extract_with_docling(data)
    if docling_result.text.strip():
        return docling_result
    failures.extend(docling_result.warnings)

    fallback_result = _extract_with_built_in_pdf_fallback(data)
    if fallback_result.text.strip():
        return fallback_result
    failures.extend(fallback_result.warnings)

    return PdfExtractionResult(
        text="",
        parser_name=BUILT_IN_PARSER_NAME,
        parser_version=BUILT_IN_PARSER_VERSION,
        parser_chain=["pypdf", "pymupdf", "docling", "built_in_fallback"],
        warnings=failures,
    )


def _has_image_pages_without_native_text(data: bytes) -> bool:
    try:
        import fitz
    except Exception:
        return False

    try:
        document = fitz.open(stream=data, filetype="pdf")
        if document.page_count == 0:
            return False
        text_length = 0
        image_pages = 0
        for page in document:
            text_length += len(page.get_text("text").strip())
            if page.get_images(full=True):
                image_pages += 1
        return text_length < PDF_MIN_TEXT_LENGTH and image_pages > 0
    except Exception:
        return False


def _extract_with_docling(data: bytes) -> PdfExtractionResult:
    parser_name = "docling"
    parser_version = _package_version("docling")
    try:
        from docling.document_converter import DocumentConverter
    except Exception as exc:
        return _pdf_parser_failure(parser_name, parser_version, exc)

    try:
        with NamedTemporaryFile(suffix=".pdf") as temp_file:
            temp_file.write(data)
            temp_file.flush()
            result = DocumentConverter().convert(temp_file.name)
        document = result.document
        text = _docling_document_to_text(document)
        segments = _segments_from_lines(text, page_count=None)
        return PdfExtractionResult(
            text=text,
            parser_name=parser_name,
            parser_version=parser_version,
            parser_chain=["pypdf", "pymupdf", parser_name],
            page_count=_page_count_from_docling_document(document),
            segments=segments,
        )
    except Exception as exc:
        return _pdf_parser_failure(parser_name, parser_version, exc)


def _docling_document_to_text(document: Any) -> str:
    for method_name in ("export_to_markdown", "export_to_text"):
        method = getattr(document, method_name, None)
        if callable(method):
            text = method()
            if isinstance(text, str):
                return text
    return str(document)


def _page_count_from_docling_document(document: Any) -> int | None:
    pages = getattr(document, "pages", None)
    if pages is None:
        return None
    try:
        return len(pages)
    except TypeError:
        return None


def _extract_with_pymupdf(data: bytes) -> PdfExtractionResult:
    parser_name = "pymupdf"
    parser_version = _package_version("pymupdf")
    try:
        import fitz
    except Exception as exc:
        return _pdf_parser_failure(parser_name, parser_version, exc)

    try:
        document = fitz.open(stream=data, filetype="pdf")
        pages: list[tuple[int, str]] = []
        for page_index, page in enumerate(document, start=1):
            page_text = page.get_text("text")
            if page_text.strip():
                pages.append((page_index, page_text))
        segments = _segments_from_page_text(pages)
        return PdfExtractionResult(
            text="\n".join(page_text.strip() for _, page_text in pages),
            parser_name=parser_name,
            parser_version=parser_version,
            parser_chain=["pypdf", parser_name],
            page_count=document.page_count,
            segments=segments,
        )
    except Exception as exc:
        return _pdf_parser_failure(parser_name, parser_version, exc)


def _extract_with_pypdf(data: bytes) -> PdfExtractionResult:
    parser_name = "pypdf"
    parser_version = _package_version("pypdf")
    try:
        from pypdf import PdfReader
    except Exception as exc:
        return _pdf_parser_failure(parser_name, parser_version, exc)

    try:
        reader = PdfReader(BytesIO(data))
        pages: list[tuple[int, str]] = []
        for page_index, page in enumerate(reader.pages, start=1):
            page_text = page.extract_text() or ""
            if page_text.strip():
                pages.append((page_index, page_text))
        segments = _segments_from_page_text(pages)
        return PdfExtractionResult(
            text="\n".join(page_text.strip() for _, page_text in pages),
            parser_name=parser_name,
            parser_version=parser_version,
            parser_chain=[parser_name],
            page_count=len(reader.pages),
            segments=segments,
        )
    except Exception as exc:
        return _pdf_parser_failure(parser_name, parser_version, exc)


def _extract_with_built_in_pdf_fallback(data: bytes) -> PdfExtractionResult:
    text = _extract_pdf_text(data)
    return PdfExtractionResult(
        text=text,
        parser_name=BUILT_IN_PARSER_NAME,
        parser_version=BUILT_IN_PARSER_VERSION,
        parser_chain=["pypdf", "pymupdf", "docling", "built_in_fallback"],
    )


def _segments_from_page_text(pages: list[tuple[int, str]]) -> list[ParsedSegment]:
    segments: list[ParsedSegment] = []
    current_section: str | None = None
    for page_number, page_text in pages:
        page_segments = _segments_from_lines(page_text, page_count=None)
        for segment in page_segments:
            if segment.section is not None:
                current_section = segment.section
            segments.append(
                ParsedSegment(
                    text=segment.text,
                    section=segment.section or current_section,
                    page_start=page_number,
                    page_end=page_number,
                )
            )
    return segments


def _pdf_parser_failure(
    parser_name: str,
    parser_version: str,
    exc: Exception,
) -> PdfExtractionResult:
    return PdfExtractionResult(
        text="",
        parser_name=parser_name,
        parser_version=parser_version,
        parser_chain=[parser_name],
        warnings=[f"{parser_name} unavailable or failed: {type(exc).__name__}"],
    )


def _package_version(package_name: str) -> str:
    try:
        from importlib.metadata import PackageNotFoundError, version
    except ImportError:
        return "unknown"
    try:
        return version(package_name)
    except PackageNotFoundError:
        return "not-installed"


def _extract_pdf_text(data: bytes) -> str:
    metadata_bytes = _remove_pdf_stream_bodies(data)
    printable = _extract_printable_text(metadata_bytes)
    lines = [
        line
        for line in printable.splitlines()
        if _looks_like_human_pdf_text(line) and not _looks_like_pdf_syntax(line)
    ]
    return "\n".join(lines)


def _remove_pdf_stream_bodies(data: bytes) -> bytes:
    return re.sub(rb"\bstream\r?\n?.*?\r?\n?endstream\b", b"\n", data, flags=re.DOTALL)


def _extract_printable_text(data: bytes) -> str:
    decoded = data.decode("utf-8", errors="ignore")
    if len(decoded.strip()) < 20:
        decoded = data.decode("latin-1", errors="ignore")
    cleaned = re.sub(r"[^\S\r\n]+", " ", decoded)
    cleaned = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]+", " ", cleaned)
    return "\n".join(line.strip() for line in cleaned.splitlines() if line.strip())


def _looks_like_human_pdf_text(line: str) -> bool:
    if len(line) < 3:
        return False
    letters = sum(character.isalpha() for character in line)
    if letters < 3:
        return False
    visible = sum(not character.isspace() for character in line)
    if visible == 0:
        return False
    punctuation = sum(not character.isalnum() and not character.isspace() for character in line)
    words = re.findall(r"[A-Za-z]{3,}", line)
    return punctuation / visible < 0.35 and (len(words) >= 2 or visible < 40)


def _looks_like_pdf_syntax(line: str) -> bool:
    stripped = line.strip()
    lowered = stripped.lower()
    if stripped.startswith("%PDF") or stripped in {"<<", ">>"}:
        return True
    if lowered in {"stream", "endstream", "endobj", "xref", "trailer", "startxref"}:
        return True
    if re.match(r"^\d+\s+\d+\s+obj\b", stripped):
        return True
    if re.search(r"\b(obj|endobj|stream|endstream)\b", stripped):
        return True
    if stripped.startswith("/") and re.search(
        r"/(Type|Subtype|Filter|Length|Resources)\b", stripped
    ):
        return True
    pdf_operator_count = len(
        re.findall(r"/(?:Type|Subtype|Filter|FlateDecode|Length|Matrix|Resources|BBox)\b", stripped)
    )
    return pdf_operator_count >= 2


def _segments_from_markdown(text: str) -> list[ParsedSegment]:
    segments: list[ParsedSegment] = []
    current_heading: str | None = None
    for index, stripped, char_start, char_end in _line_records(text):
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            current_heading = heading_match.group(2).strip()
        if stripped:
            segments.append(
                ParsedSegment(
                    text=stripped,
                    section=current_heading,
                    line_start=index,
                    line_end=index,
                    char_start=char_start,
                    char_end=char_end,
                )
            )
    return segments


def _segments_from_lines(text: str, page_count: int | None) -> list[ParsedSegment]:
    segments: list[ParsedSegment] = []
    current_section: str | None = None
    line_records = _line_records(text)
    line_count = len(line_records)
    for index, stripped, char_start, char_end in line_records:
        if not stripped:
            continue
        detected_heading = _detect_heading(stripped)
        if detected_heading is not None:
            current_section = detected_heading
        page_number = _line_to_page(index, line_count, page_count)
        segments.append(
            ParsedSegment(
                text=stripped,
                section=current_section,
                page_start=page_number,
                page_end=page_number,
                line_start=index if page_count is None else None,
                line_end=index if page_count is None else None,
                char_start=char_start,
                char_end=char_end,
            )
        )
    return segments


def _line_records(text: str) -> list[tuple[int, str, int, int]]:
    records: list[tuple[int, str, int, int]] = []
    offset = 0
    for index, raw_line in enumerate(text.splitlines(keepends=True), start=1):
        line_without_break = raw_line.rstrip("\r\n")
        stripped = line_without_break.strip()
        leading = len(line_without_break) - len(line_without_break.lstrip())
        char_start = offset + leading
        char_end = char_start + len(stripped)
        records.append((index, stripped, char_start, char_end))
        offset += len(raw_line)
    if text and not records:
        stripped = text.strip()
        leading = len(text) - len(text.lstrip())
        records.append((1, stripped, leading, leading + len(stripped)))
    return records


def _detect_heading(line: str) -> str | None:
    if len(line) > 120:
        return None
    if re.match(r"^(\d+(\.\d+)*\.?\s+)?[A-Z][A-Za-z0-9 ,:/()%-]{2,}$", line):
        return line.rstrip(".")
    lowered = line.lower()
    if lowered in {
        "abstract",
        "claims",
        "description",
        "detailed description",
        "examples",
        "references",
        "background",
        "summary",
    }:
        return line
    return None


def _line_to_page(index: int, line_count: int, page_count: int | None) -> int | None:
    if page_count is None:
        return None
    if line_count <= 1:
        return 1
    page = int(((index - 1) / line_count) * page_count) + 1
    return min(page, page_count)


def _unique_sections(segments: list[ParsedSegment]) -> list[str]:
    seen: set[str] = set()
    sections: list[str] = []
    for segment in segments:
        if segment.section and segment.section not in seen:
            seen.add(segment.section)
            sections.append(segment.section)
    return sections


def _detect_patent_sections(text: str) -> list[str]:
    return [name for name, pattern in _PATENT_SECTION_PATTERNS if pattern.search(text)]


def _detect_scientific_structure_hints(text: str) -> list[str]:
    patterns: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("tables", re.compile(r"\b(table|tab\.)\s+\d+", re.IGNORECASE)),
        ("figures", re.compile(r"\b(fig\.|figure)\s+\d+", re.IGNORECASE)),
        ("captions", re.compile(r"\b(caption|scheme)\s+\d+", re.IGNORECASE)),
    )
    return [name for name, pattern in patterns if pattern.search(text)]
