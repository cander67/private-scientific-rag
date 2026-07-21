from __future__ import annotations

import hashlib
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

PageOcrClassification = Literal["born_digital", "scanned", "mixed"]
OcrStatus = Literal["not_required", "pending", "missing_dependency"]

OCR_MIN_NATIVE_TEXT_LENGTH = 80
OCR_MIXED_TEXT_LENGTH = 20
OCR_RENDER_SCALE = 2.0

OCR_QUALITY_THRESHOLDS = {
    "min_native_text_length": OCR_MIN_NATIVE_TEXT_LENGTH,
    "mixed_text_length": OCR_MIXED_TEXT_LENGTH,
    "render_scale": OCR_RENDER_SCALE,
}


@dataclass(frozen=True)
class PageOcrRoute:
    page: int
    classification: PageOcrClassification
    text_length: int
    word_count: int
    image_count: int
    quality_score: float
    needs_ocr: bool
    warnings: list[str] = field(default_factory=list)

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class OcrPageImage:
    page: int
    path: str
    mime_type: str
    width: int
    height: int
    byte_size: int
    sha256: str
    renderer: str
    source_sha256: str

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


@dataclass(frozen=True)
class NormalizedOcrPageResult:
    page: int
    text: str
    confidence: float | None
    warnings: list[str]
    provider: dict[str, object]
    provenance: dict[str, object]

    def to_metadata(self) -> dict[str, object]:
        return asdict(self)


def classify_page_for_ocr(
    *,
    page: int,
    text: str,
    image_count: int,
    min_native_text_length: int = OCR_MIN_NATIVE_TEXT_LENGTH,
    mixed_text_length: int = OCR_MIXED_TEXT_LENGTH,
) -> PageOcrRoute:
    normalized_text = text.strip()
    text_length = len(normalized_text)
    word_count = len(normalized_text.split())
    if text_length >= min_native_text_length and image_count == 0:
        return PageOcrRoute(
            page=page,
            classification="born_digital",
            text_length=text_length,
            word_count=word_count,
            image_count=image_count,
            quality_score=1.0,
            needs_ocr=False,
        )
    if text_length >= min_native_text_length:
        return PageOcrRoute(
            page=page,
            classification="mixed",
            text_length=text_length,
            word_count=word_count,
            image_count=image_count,
            quality_score=0.85,
            needs_ocr=False,
            warnings=["Page contains native text and images; OCR is not required."],
        )
    if image_count > 0 and text_length < mixed_text_length:
        return PageOcrRoute(
            page=page,
            classification="scanned",
            text_length=text_length,
            word_count=word_count,
            image_count=image_count,
            quality_score=0.1,
            needs_ocr=True,
            warnings=["Page appears image-only and is pending OCR."],
        )
    if image_count > 0:
        return PageOcrRoute(
            page=page,
            classification="mixed",
            text_length=text_length,
            word_count=word_count,
            image_count=image_count,
            quality_score=0.45,
            needs_ocr=True,
            warnings=["Page has limited native text plus images and is pending OCR."],
        )
    return PageOcrRoute(
        page=page,
        classification="born_digital",
        text_length=text_length,
        word_count=word_count,
        image_count=image_count,
        quality_score=0.35,
        needs_ocr=True,
        warnings=["Page has limited native text and should be inspected before indexing OCR text."],
    )


def classify_pdf_pages(data: bytes) -> tuple[list[PageOcrRoute], list[str]]:
    try:
        import fitz
    except Exception as exc:
        return [], [f"OCR page routing unavailable: PyMuPDF import failed ({type(exc).__name__})."]

    try:
        document = fitz.open(stream=data, filetype="pdf")
        routes = [
            classify_page_for_ocr(
                page=page_index,
                text=page.get_text("text"),
                image_count=len(page.get_images(full=True)),
            )
            for page_index, page in enumerate(document, start=1)
        ]
        return routes, []
    except Exception as exc:
        return [], [f"OCR page routing unavailable: PDF inspection failed ({type(exc).__name__})."]


def ocr_status_from_routes(
    routes: list[PageOcrRoute],
    warnings: list[str] | None = None,
) -> dict[str, object]:
    route_warnings = warnings or []
    pending_pages = [route.page for route in routes if route.needs_ocr]
    status: OcrStatus = "pending" if pending_pages else "not_required"
    if route_warnings and not routes:
        status = "missing_dependency"
    return {
        "status": status,
        "pages_pending": pending_pages,
        "pages_routed": len(routes),
        "warnings": route_warnings,
    }


def render_pages_for_ocr(
    *,
    data: bytes,
    routes: list[PageOcrRoute],
    destination_dir: Path,
    source_sha256: str | None = None,
) -> tuple[list[OcrPageImage], list[str]]:
    pages_to_render = [route.page for route in routes if route.needs_ocr]
    if not pages_to_render:
        return [], []
    try:
        import fitz
    except Exception as exc:
        return [], [
            f"OCR page rendering unavailable: PyMuPDF import failed ({type(exc).__name__})."
        ]

    destination_dir.mkdir(parents=True, exist_ok=True)
    source_digest = source_sha256 or hashlib.sha256(data).hexdigest()
    try:
        document = fitz.open(stream=data, filetype="pdf")
        rendered: list[OcrPageImage] = []
        for page_number in pages_to_render:
            if page_number < 1 or page_number > document.page_count:
                continue
            page = document.load_page(page_number - 1)
            pixmap = page.get_pixmap(
                matrix=fitz.Matrix(OCR_RENDER_SCALE, OCR_RENDER_SCALE), alpha=False
            )
            destination = destination_dir / f"ocr-page-{page_number:04d}.png"
            pixmap.save(destination)
            image_bytes = destination.read_bytes()
            rendered.append(
                OcrPageImage(
                    page=page_number,
                    path=str(destination),
                    mime_type="image/png",
                    width=pixmap.width,
                    height=pixmap.height,
                    byte_size=len(image_bytes),
                    sha256=hashlib.sha256(image_bytes).hexdigest(),
                    renderer="pymupdf",
                    source_sha256=source_digest,
                )
            )
        return rendered, []
    except Exception as exc:
        return [], [f"OCR page rendering failed: {type(exc).__name__}."]


def normalize_ocr_page_result(
    *,
    page: int,
    text: str,
    confidence: float | None,
    provider_name: str,
    provider_version: str,
    image: OcrPageImage | None = None,
    warnings: list[str] | None = None,
    provider_metadata: dict[str, object] | None = None,
) -> NormalizedOcrPageResult:
    provenance: dict[str, object] = {"page": page}
    if image is not None:
        provenance.update(
            {
                "image_sha256": image.sha256,
                "image_path": image.path,
                "renderer": image.renderer,
                "source_sha256": image.source_sha256,
            }
        )
    provider: dict[str, object] = {
        "name": provider_name,
        "version": provider_version,
    }
    if provider_metadata:
        provider["metadata"] = provider_metadata
    return NormalizedOcrPageResult(
        page=page,
        text=text,
        confidence=confidence,
        warnings=warnings or [],
        provider=provider,
        provenance=provenance,
    )


def missing_ocr_dependency_result(
    *,
    page: int,
    provider_name: str,
    dependency_name: str,
    image: OcrPageImage | None = None,
) -> NormalizedOcrPageResult:
    return normalize_ocr_page_result(
        page=page,
        text="",
        confidence=None,
        provider_name=provider_name,
        provider_version="not-installed",
        image=image,
        warnings=[f"{dependency_name} is not installed; OCR is pending for page {page}."],
    )
