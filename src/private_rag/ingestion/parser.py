from __future__ import annotations

import re
from pathlib import Path

from private_rag.ingestion.schemas import ParsedDocument, ParsedSegment, SourceType

PARSER_NAME = "private-rag-built-in"
PARSER_VERSION = "prd3-v1"

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
    text = _extract_printable_text(data)
    page_count = max(1, len(re.findall(rb"/Type\s*/Page\b", data)))
    warnings: list[str] = []
    ocr_required = False
    if len(text.strip()) < 80:
        ocr_required = True
        warnings.append(
            "PDF has little extractable text and should be inspected with OCR/page images."
        )

    segments = _segments_from_lines(text, page_count=page_count)
    sections = _unique_sections(segments)
    patent_sections = _detect_patent_sections(text)
    metadata: dict[str, object] = {
        "page_images_available": True,
        "patent_section_hints": patent_sections,
    }
    if patent_sections:
        metadata["document_kind"] = "patent_pdf"

    return ParsedDocument(
        source_type="pdf",
        text=text,
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
        segments=segments,
        line_count=len(text.splitlines()),
        sections=_unique_sections(segments),
        metadata={"line_provenance": True},
    )


def _parse_annotation(data: bytes) -> ParsedDocument:
    text = _decode(data)
    lines = text.splitlines()
    segments = [
        ParsedSegment(
            text=line,
            section="annotations",
            line_start=index,
            line_end=index,
            metadata={"annotation_format": "brat_standoff"},
        )
        for index, line in enumerate(lines, start=1)
        if line.strip()
    ]
    return ParsedDocument(
        source_type="annotation",
        text=text,
        segments=segments,
        line_count=len(lines),
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
        segments=segments,
        line_count=len(text.splitlines()),
        sections=_unique_sections(segments),
        metadata={"line_provenance": True},
    )


def _decode(data: bytes) -> str:
    return data.decode("utf-8", errors="replace")


def _extract_printable_text(data: bytes) -> str:
    decoded = data.decode("utf-8", errors="ignore")
    if len(decoded.strip()) < 20:
        decoded = data.decode("latin-1", errors="ignore")
    cleaned = re.sub(r"[^\S\r\n]+", " ", decoded)
    cleaned = re.sub(r"[^\x09\x0A\x0D\x20-\x7E]+", " ", cleaned)
    return "\n".join(line.strip() for line in cleaned.splitlines() if line.strip())


def _segments_from_markdown(text: str) -> list[ParsedSegment]:
    segments: list[ParsedSegment] = []
    current_heading: str | None = None
    for index, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        heading_match = re.match(r"^(#{1,6})\s+(.+)$", stripped)
        if heading_match:
            current_heading = heading_match.group(2).strip()
        if stripped:
            segments.append(
                ParsedSegment(
                    text=line,
                    section=current_heading,
                    line_start=index,
                    line_end=index,
                )
            )
    return segments


def _segments_from_lines(text: str, page_count: int | None) -> list[ParsedSegment]:
    segments: list[ParsedSegment] = []
    current_section: str | None = None
    lines = text.splitlines()
    for index, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not stripped:
            continue
        detected_heading = _detect_heading(stripped)
        if detected_heading is not None:
            current_section = detected_heading
        page_number = _line_to_page(index, len(lines), page_count)
        segments.append(
            ParsedSegment(
                text=stripped,
                section=current_section,
                page_start=page_number,
                page_end=page_number,
                line_start=index if page_count is None else None,
                line_end=index if page_count is None else None,
            )
        )
    return segments


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
