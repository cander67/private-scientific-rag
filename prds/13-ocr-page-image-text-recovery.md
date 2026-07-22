# PRD 13: Parser Selection, OCR, and Page-Image Text Recovery

**Status:** Ready for final review. Parser routing, reprocess, stale-index freshness gates, local OCR recovery, RapidOCR fallback, chunking remediation, parser-label clarity, and documentation preparation are implemented with deterministic checks passing; optional OCR dependency and golden-corpus checks remain opt-in. PRD13 is not marked complete until user acceptance and the PRD29 manual acceptance pass.

## Problem Statement

PRD3 can preserve page thumbnails and mark image-only or low-text PDFs as `needs_ocr`, but researchers still cannot recover searchable text from scanned patents, scanned scientific papers, page-image PDFs, or poorly encoded PDFs. Those documents remain inspectable but not meaningfully retrievable.

PRD26 makes parser choices visible and validated in Settings / Models, but the ingestion pipeline still uses a hard-coded PDF parser chain. Researchers can save parser settings such as `Auto`, PyMuPDF, Docling, pdfplumber, pypdf, built-in fallback, `needs_ocr`, OCRmyPDF/Tesseract, and RapidOCR, but upload and reprocess behavior does not yet honor those choices.

The system needs a local-first parser routing and OCR pipeline that uses repository parser settings during ingestion and reprocessing, turns page images into auditable text when OCR is explicitly run, and records enough parser/OCR settings metadata to know when existing chunks are stale.

## Solution

Implement a repository-scoped parser execution layer that wires the full PRD26 parser choices into document upload, document reprocess, and index rebuild workflows. `Auto` should preserve the current safe default parser behavior while explicit parser choices should constrain or reorder the parser route in a reproducible way. OCR should remain local-first, inspectable, and recoverable.

Add an opt-in local OCR pipeline for PDF page images and image-heavy documents. OCR should run per page, preserve page/image provenance, create reviewable OCR text artifacts, and re-enter the existing parse/chunk/source-inspection flow. The first implementation should prioritize reliable local OCR for English scientific and patent PDFs, clear confidence metadata, safe parser fallback behavior, and deterministic CI over perfect recognition.

The roadmap should build on PRD3 page-thumbnail work and PRD26 parser controls:

1. Preserve PRD3 behavior under `Auto`: render page thumbnails, try the current local parser chain, mark low-text PDFs as `needs_ocr`, and keep source inspection useful even before OCR.
2. Introduce parser execution settings that are passed from repository settings into upload and reprocess, and recorded on document versions/chunks.
3. Support explicit parser routing for PyMuPDF, Docling, pdfplumber, pypdf, built-in fallback, `needs_ocr`, OCRmyPDF/Tesseract, and RapidOCR where implemented, with clear warnings when optional dependencies or OCR providers are unavailable.
4. Add an OCR adapter boundary with a normalized page result model.
5. Use page-level routing to classify born-digital text pages, scanned/image-only pages, and mixed pages.
6. Render only pages that need OCR, preferring a local renderer such as `pypdfium2` for OCR input images.
7. Use OCRmyPDF plus Tesseract as the stable baseline OCR path because it is local, mature, CPU-friendly, and produces searchable/auditable PDFs.
8. Add RapidOCR as an optional fallback for pages where Tesseract confidence or text quality is poor.
9. Store parser runs, OCR text, confidence, bounding boxes where available, warnings, and provider metadata as derived artifacts.
10. Convert OCR page artifacts into page-aware chunks only after preserving the raw OCR output for inspection.
11. Add Source Viewer review of OCR text beside page thumbnails before making OCR-backed retrieval feel automatic.
12. Evaluate PaddleOCR, Marker, Surya, and olmOCR later for layout-rich scientific PDFs, scanned tables, equations, and difficult reading order.

## User Stories

1. As a researcher, I can upload a document using the repository's saved parser settings, so that parser choices are reproducible instead of decorative.
2. As a researcher, I can choose `Auto` and get the app's safest default parser chain, so that ordinary ingestion remains low-friction.
3. As a researcher, I can choose an explicit parser route such as PyMuPDF, Docling, pdfplumber, pypdf, or built-in fallback, so that ingestion behavior is controlled and auditable.
4. As a researcher, I can OCR a document marked `needs_ocr`, so that scanned PDFs become searchable without re-uploading them.
5. As a researcher, I can inspect OCR text beside the page thumbnail, so that I can judge whether the recovered text is trustworthy.
6. As a researcher, I can see parser/OCR confidence and warnings per page or document, so that weak pages do not silently pollute retrieval.
7. As a researcher, I can reprocess parsing or OCR after changing parser, fallback, OCR, or chunking settings, so that improved settings can update a document without re-uploading it.
8. As a researcher, I can rebuild full-text/vector indexes after parser or chunking changes, so that search uses the latest parsed chunks rather than stale upload-time chunks.
9. As a researcher, I can keep OCR fully local, so that private documents do not leave my machine.
10. As a researcher, I can search patent drawings and scanned claims after OCR, so that image-only patent PDFs are no longer invisible to retrieval.
11. As a maintainer, I can disable OCR when local dependencies are missing, so that normal ingestion still works.
12. As a maintainer, I can test parser routing and OCR with tiny deterministic fixtures, so that CI does not depend on large documents or external services.

## Scope

- Parser execution settings passed from repository settings into document upload, document reprocess, OCR action, and reindex/rebuild workflows.
- Operational support for the PRD26 parser catalog: `auto`, `pymupdf`, `docling`, `pdfplumber`, `pypdf`, `built_in_fallback`, `needs_ocr`, `ocrmypdf_tesseract`, and `rapidocr`.
- Parser route semantics:
  - `auto` preserves the current safe local chain: pypdf, PyMuPDF, image-only/low-text OCR gate, Docling, built-in fallback.
  - Explicit structured parser choices run the chosen parser first and then use the configured fallback parser when extraction quality or dependency checks fail.
  - `needs_ocr` is a routing gate that marks OCR-required documents without silently running OCR.
  - OCR providers run only through explicit OCR/reprocess actions or OCR-enabled settings, not as hidden upload side effects.
- Parser run fingerprinting that includes structured parser, fallback parser, OCR provider/settings, chunking mode/size/overlap, parser package versions where available, source hash, and relevant quality thresholds.
- Document-version and chunk metadata that records the parser route actually used, fallback decisions, OCR provider/version where applicable, settings fingerprint, warnings, and stale/reprocess status.
- Reprocess behavior that can rerun parsing, OCR, chunking, and downstream full-text/vector rebuild preparation without re-uploading the source document.
- Reindex/rebuild behavior that detects when chunking or parser choices differ from the parser fingerprint used by the latest parsed document version and either blocks, warns, or creates a new parse/chunk version before index rebuild.
- Local OCR adapter interface with provider name, version, settings, per-page output, confidence, and warnings.
- Page-type detection that routes each page as born-digital, scanned/image-only, or mixed.
- Page rendering for OCR with a local renderer, preferably `pypdfium2`, and only for pages that need OCR.
- First baseline OCR path through OCRmyPDF plus Tesseract.
- Optional fallback OCR path through RapidOCR after baseline OCR confidence or quality checks fail.
- OCR job action for documents that are `needs_ocr`, low-text, image-heavy, parser-failed, or explicitly selected by the user.
- Per-page OCR artifacts stored separately from source files, page images, chunks, parser metadata, and indexes.
- Merge path that converts OCR output into parsed segments and chunks with page provenance.
- Source Viewer support for parser route, page thumbnail, OCR text, OCR confidence, OCR warnings, stale parser/chunk status, and OCR-backed chunk citations.
- Repository settings for OCR enablement, language, page image scale, confidence threshold, max pages, overwrite behavior, and fallback provider behavior.
- Golden corpus smoke coverage for `patent-ocr-stress.pdf` and at least one synthetic image-only fixture.
- Later evaluation branch for PaddleOCR, Marker, Surya, and olmOCR after the baseline local parser/OCR path is proven.

## Non-Goals

- Hosted/cloud OCR.
- Handwriting recognition.
- Guaranteed perfect formulas, tables, claims, or chemical nomenclature recognition.
- Image-to-chemical-structure recognition.
- Full layout reconstruction beyond page-level text and basic line ordering.
- OCR for arbitrary image collections outside the document-ingestion path.
- Making OCRmyPDF, Tesseract, RapidOCR, pdfplumber, PaddleOCR, Marker, Surya, or olmOCR required MVP dependencies.
- Full PRD14 table artifact extraction, table correction, or table-specific retrieval ranking. PRD13 may route through pdfplumber and preserve parser metadata, but PRD14 owns durable table artifacts and table-backed chunks.
- Automatic destructive replacement of prior parse artifacts without a visible reprocess/versioning path.

## Acceptance Criteria

- Document upload passes repository parser settings into the parser execution layer.
- `Auto` upload and reprocess preserve the current PRD3 parser behavior and parser-chain metadata.
- Explicit parser choices change the parser route in a reproducible way, record the route actually used, and produce visible warnings when dependencies are unavailable or extraction quality falls through to fallback.
- The latest document version records parser/chunking/OCR settings fingerprint metadata sufficient to determine whether saved settings have changed since parsing.
- Reprocess can rerun parsing and chunking from the stored source file without re-uploading the document.
- Reprocess can rerun OCR after parser/OCR settings changes without deleting the original source, prior page thumbnails, or prior parser output.
- Full-text/vector rebuild workflows detect stale parser/chunk fingerprints and guide the user to reprocess before indexing stale chunks, or explicitly rebuild from the refreshed parse output when reprocess is part of the workflow.
- A `needs_ocr` PDF can be OCRed locally and returns to an inspectable parsed state with OCR-backed chunks.
- OCR chunks include repository ID, document ID, document version ID, page range, parser/OCR version, source-file hash, page-image hash where available, offsets or line ranges where available, confidence metadata, parser settings fingerprint, and warnings.
- Source Viewer shows parser route, parser warnings, OCR text, OCR confidence, stale/reprocess status, and OCR-derived labels next to page thumbnails.
- Low-confidence pages remain visible and are not silently treated as high-quality parsed text.
- OCR failures are visible, recoverable, and do not delete the original source or previous parse artifacts.
- OCR remains local-first and does not require network access.
- Golden corpus smoke tests verify the OCR stress fixture produces page images, OCR status metadata, and at least one inspectable OCR artifact when OCR dependencies are available.
- OCR output can be disabled, rerun, or discarded without deleting PRD3 page thumbnails or the original parser output.

## Implementation Decisions

- Treat parser execution as a small adapter/router layer rather than letting upload call individual parser helpers directly.
- Treat OCR as a derived parse layer, not as a replacement for the original source file.
- Store OCR artifacts separately from page images so page rendering, OCR text, and chunks can be audited independently.
- Keep parser and OCR provider details behind adapter interfaces so pypdf, PyMuPDF, Docling, pdfplumber, built-in fallback, OCRmyPDF/Tesseract, and RapidOCR can be replaced or augmented later.
- Record both parser version and OCR provider/version in metadata because scanned PDFs pass through rendering and recognition steps.
- Treat OCRmyPDF plus Tesseract as the baseline provider for the first implementation, and RapidOCR as an optional fallback provider.
- Prefer `pypdfium2` for OCR page rendering so rendering is local, explicit, and separated from text extraction.
- Gate OCR execution through repository settings and explicit user action first; automatic OCR can be added later after performance is understood.
- Use existing document reprocess semantics where possible, but preserve a clear distinction between parser reprocess and OCR reprocess.
- Keep OCR output page-aware before chunking so chat citations can refer back to a page thumbnail.
- Treat pdfplumber as complementary to OCR, not an OCR provider. It may improve layout/table/image metadata for machine-generated PDFs before OCR exists, but scanned-page recovery still belongs to the OCR adapter path.
- Do not accept OCR output into retrieval solely because a text layer exists. Score text quality with character count, word count, unusual-character ratio, whitespace quality, repeated glyph artifacts, and confidence where available.
- Do not silently index stale chunks after parser or chunking settings change. The UI/API should make stale parse state visible and require reprocess or an explicit refresh path.

## Testing Decisions

- Unit test parser route construction for `auto`, explicit structured parser choices, explicit fallback parser choices, OCR gates, dependency-missing paths, and extraction-quality fallback.
- Unit test parser settings fingerprint generation and stale parser/chunk detection.
- Unit test upload and reprocess services pass repository parser settings into parser execution.
- Unit test OCR adapter result normalization with synthetic page-image outputs.
- Unit test confidence threshold behavior, warning propagation, and chunk metadata.
- Unit test page routing between native/pdfplumber extraction, OCR rendering, Tesseract baseline OCR, and RapidOCR fallback decisions.
- Integration test upload with explicit parser settings changes parser-route metadata while preserving `Auto` behavior.
- Integration test parser/chunking settings changes produce stale/reprocess guidance before full-text/vector rebuild uses old chunks.
- Integration test upload of a low-text PDF, OCR action, inspect response, and page/OCR artifact retrieval.
- Integration test OCR dependency missing path returns a visible recoverable warning rather than failing ingestion.
- Frontend contract tests should cover parser route/stale status, reprocess actions, OCR action state, OCR text inspection, and index rebuild warnings.
- Golden corpus tests should be optional or marked when they require installed OCR binaries.
- Tests should assert external document status, artifacts, warnings, parser route metadata, and provenance fields rather than OCR engine internals.
- Add dependency-available smoke tests for OCRmyPDF/Tesseract, pdfplumber, and RapidOCR fallback, but keep core CI green when optional parser/OCR providers are missing or disabled.

## Out of Scope

PRD13 does not implement full OCR quality evaluation, human correction workflows, model-based document understanding, or PRD14 table artifact extraction. It closes the PRD3 and PRD26 gaps where image-only documents were inspectable but not searchable, and parser settings were selectable but not yet operational.

## Further Notes

Start with parser routing and settings fingerprints before OCR execution. A useful first milestone is: `Auto` keeps existing parser behavior, an explicit parser choice changes recorded parser-route metadata, and reprocess/index rebuild flows can identify stale parse settings without requiring OCR dependencies.

Then add page routing, `pypdfium2` rendering, OCRmyPDF/Tesseract baseline OCR, and one end-to-end UI path for `needs_ocr` documents. Once that is stable, add RapidOCR fallback, language settings, larger golden corpus runs, and retrieval evaluation against scanned patent and scientific fixtures. Keep PaddleOCR, Marker, Surya, and olmOCR as benchmark/evaluation tools until the simple local stack is proven.

## Final Review Summary

PRD13 is ready for final review with the implementation plan fully checked off. The delivered scope includes repository parser and chunking settings applied during upload/reprocess, fixed and recursive chunk output with chunk metadata, versioned reprocess from stored sources, parser/chunk fingerprint stale detection before full-text/vector rebuilds, page OCR routing, explicit local OCR recovery, OCR-derived page artifacts/chunks, optional RapidOCR fallback, repository OCR quality controls, Source Viewer parser/OCR labels, and deterministic test coverage.

Optional OCR dependency and golden-corpus smoke checks remain manual because they depend on local host binaries and corpus availability. PRD29 defines the manual acceptance pass for those checks. PRD13 remains ready for review, not complete, until accepted by the user.
