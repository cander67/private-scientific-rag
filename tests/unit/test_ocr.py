from __future__ import annotations

import builtins
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

from private_rag.ingestion.ocr import (
    OcrPageImage,
    classify_page_for_ocr,
    classify_pdf_pages,
    missing_ocr_dependency_result,
    normalize_ocr_page_result,
    ocr_status_from_routes,
    render_pages_for_ocr,
)


def test_page_routing_classifies_born_digital_scanned_and_mixed_pages() -> None:
    born_digital = classify_page_for_ocr(
        page=1,
        text="Abstract " + "native searchable text " * 12,
        image_count=0,
    )
    scanned = classify_page_for_ocr(page=2, text="", image_count=1)
    mixed_pending = classify_page_for_ocr(
        page=3,
        text="Figure 1 contains sparse caption text",
        image_count=2,
    )
    mixed_native = classify_page_for_ocr(
        page=4,
        text="Figure 2 " + "native searchable text " * 12,
        image_count=1,
    )

    assert born_digital.classification == "born_digital"
    assert born_digital.quality_score == 1.0
    assert born_digital.needs_ocr is False
    assert scanned.classification == "scanned"
    assert scanned.needs_ocr is True
    assert mixed_pending.classification == "mixed"
    assert mixed_pending.needs_ocr is True
    assert mixed_native.classification == "mixed"
    assert mixed_native.needs_ocr is False


def test_page_routing_thresholds_are_deterministic() -> None:
    below_threshold = classify_page_for_ocr(
        page=1,
        text="x" * 79,
        image_count=0,
        min_native_text_length=80,
    )
    at_threshold = classify_page_for_ocr(
        page=2,
        text="x" * 80,
        image_count=0,
        min_native_text_length=80,
    )

    assert below_threshold.needs_ocr is True
    assert below_threshold.quality_score == 0.35
    assert at_threshold.needs_ocr is False
    assert at_threshold.quality_score == 1.0


def test_ocr_status_reports_pending_pages_and_dependency_warnings() -> None:
    routes = [
        classify_page_for_ocr(page=1, text="native text " * 12, image_count=0),
        classify_page_for_ocr(page=2, text="", image_count=1),
    ]

    assert ocr_status_from_routes(routes) == {
        "status": "pending",
        "pages_pending": [2],
        "pages_routed": 2,
        "warnings": [],
    }
    assert ocr_status_from_routes([], ["PyMuPDF missing"]) == {
        "status": "missing_dependency",
        "pages_pending": [],
        "pages_routed": 0,
        "warnings": ["PyMuPDF missing"],
    }


def test_normalized_ocr_result_preserves_provider_and_page_provenance() -> None:
    image = OcrPageImage(
        page=3,
        path="/tmp/ocr-page-0003.png",
        mime_type="image/png",
        width=1200,
        height=1600,
        byte_size=42,
        sha256="image-hash",
        renderer="pymupdf",
        source_sha256="source-hash",
    )

    result = normalize_ocr_page_result(
        page=3,
        text="Recovered OCR text",
        confidence=0.91,
        provider_name="tesseract",
        provider_version="5.4.0",
        image=image,
        warnings=["low contrast"],
        provider_metadata={"language": "eng"},
    )

    assert result.page == 3
    assert result.text == "Recovered OCR text"
    assert result.confidence == 0.91
    assert result.provider == {
        "name": "tesseract",
        "version": "5.4.0",
        "metadata": {"language": "eng"},
    }
    assert result.provenance == {
        "page": 3,
        "image_sha256": "image-hash",
        "image_path": "/tmp/ocr-page-0003.png",
        "renderer": "pymupdf",
        "source_sha256": "source-hash",
    }


def test_missing_ocr_dependency_result_is_recoverable_warning() -> None:
    result = missing_ocr_dependency_result(
        page=2,
        provider_name="ocrmypdf_tesseract",
        dependency_name="ocrmypdf",
    )

    assert result.text == ""
    assert result.confidence is None
    assert result.provider == {"name": "ocrmypdf_tesseract", "version": "not-installed"}
    assert result.warnings == ["ocrmypdf is not installed; OCR is pending for page 2."]


def test_classify_pdf_pages_reports_missing_local_renderer_dependency(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    real_import = builtins.__import__

    def fake_import(name: str, *args: Any, **kwargs: Any) -> object:
        if name == "fitz":
            raise ImportError("no fitz")
        return real_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", fake_import)

    routes, warnings = classify_pdf_pages(b"%PDF")

    assert routes == []
    assert warnings == ["OCR page routing unavailable: PyMuPDF import failed (ImportError)."]


def test_render_pages_for_ocr_renders_only_pending_pages(tmp_path: Path) -> None:
    fitz = pytest.importorskip("fitz")
    document = fitz.open()
    page_one = document.new_page(width=200, height=260)
    page_one.insert_text((36, 72), "Native text page")
    page_two = document.new_page(width=200, height=260)
    page_two.insert_text((36, 72), "Scanned source image")
    pixmap = page_two.get_pixmap(matrix=fitz.Matrix(1, 1), alpha=False)
    page_two.insert_image(page_two.rect, pixmap=pixmap)
    data = BytesIO()
    document.save(data)

    routes = [
        classify_page_for_ocr(page=1, text="Native text " * 10, image_count=0),
        classify_page_for_ocr(page=2, text="", image_count=1),
    ]

    rendered, warnings = render_pages_for_ocr(
        data=data.getvalue(),
        routes=routes,
        destination_dir=tmp_path,
        source_sha256="source-hash",
    )

    assert warnings == []
    assert [image.page for image in rendered] == [2]
    assert rendered[0].renderer == "pymupdf"
    assert rendered[0].source_sha256 == "source-hash"
    assert Path(rendered[0].path).exists()
