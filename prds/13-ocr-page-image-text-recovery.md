# PRD 13: OCR and Page-Image Text Recovery

## Problem Statement

PRD3 can preserve page thumbnails and mark image-only or low-text PDFs as `needs_ocr`, but researchers still cannot recover searchable text from scanned patents, scanned scientific papers, page-image PDFs, or poorly encoded PDFs. Those documents remain inspectable but not meaningfully retrievable. The system needs a local-first OCR pipeline that turns page images into auditable text, chunks, warnings, and citations without sending private documents to external services.

## Solution

Add an opt-in local OCR pipeline for PDF page images and image-heavy documents. OCR should run per page, preserve page/image provenance, create reviewable OCR text artifacts, and re-enter the existing parse/chunk/source-inspection flow. The first implementation should prioritize reliable local OCR for English scientific and patent PDFs, clear confidence metadata, and safe fallback behavior over perfect recognition.

The roadmap should build on the PRD3 page-thumbnail work:

1. Preserve PRD3 behavior: render page thumbnails, mark low-text PDFs as `needs_ocr`, and keep source inspection useful even before OCR.
2. Add an OCR adapter boundary with a normalized page result model.
3. Use page-level routing to classify born-digital text pages, scanned/image-only pages, and mixed pages.
4. Render only pages that need OCR, preferring a local renderer such as `pypdfium2` for OCR input images.
5. Use OCRmyPDF plus Tesseract as the stable baseline OCR path because it is local, mature, CPU-friendly, and produces searchable/auditable PDFs.
6. Add RapidOCR as an optional fallback for pages where Tesseract confidence or text quality is poor.
7. Store OCR text, confidence, bounding boxes where available, warnings, and provider metadata as derived page artifacts.
8. Convert OCR page artifacts into page-aware chunks only after preserving the raw OCR output for inspection.
9. Add Source Viewer review of OCR text beside page thumbnails before making OCR-backed retrieval feel automatic.
10. Evaluate PaddleOCR, Marker, Surya, and olmOCR later for layout-rich scientific PDFs, scanned tables, equations, and difficult reading order.

## User Stories

1. As a researcher, I can OCR a document marked `needs_ocr`, so that scanned PDFs become searchable without re-uploading them.
2. As a researcher, I can inspect OCR text beside the page thumbnail, so that I can judge whether the recovered text is trustworthy.
3. As a researcher, I can see OCR confidence and warnings per page, so that weak pages do not silently pollute retrieval.
4. As a researcher, I can reprocess OCR after changing OCR settings, so that improved page rendering or language settings can update a document.
5. As a researcher, I can keep OCR fully local, so that private documents do not leave my machine.
6. As a researcher, I can search patent drawings and scanned claims after OCR, so that image-only patent PDFs are no longer invisible to retrieval.
7. As a maintainer, I can disable OCR when local dependencies are missing, so that normal ingestion still works.
8. As a maintainer, I can test OCR with tiny deterministic fixtures, so that CI does not depend on large documents or external services.

## Scope

- Local OCR adapter interface with provider name, version, settings, per-page output, confidence, and warnings.
- Page-type detection that routes each page as born-digital, scanned/image-only, or mixed.
- Page rendering for OCR with a local renderer, preferably `pypdfium2`, and only for pages that need OCR.
- First baseline OCR path through OCRmyPDF plus Tesseract.
- Optional fallback OCR path through RapidOCR after baseline OCR confidence or quality checks fail.
- OCR job action for documents that are `needs_ocr`, low-text, image-heavy, or explicitly selected by the user.
- Per-page OCR artifacts stored separately from source files, page images, chunks, and parser metadata.
- Merge path that converts OCR output into parsed segments and chunks with page provenance.
- Source Viewer support for page thumbnail, OCR text, OCR confidence, OCR warnings, and OCR-backed chunk citations.
- Repository settings for OCR enablement, language, page image scale, confidence threshold, max pages, and overwrite behavior.
- Reprocess behavior that can rerun OCR without re-uploading the source document.
- Golden corpus smoke coverage for `patent-ocr-stress.pdf` and at least one synthetic image-only fixture.
- Later evaluation branch for PaddleOCR, Marker, Surya, and olmOCR after the baseline local OCR path is proven.

## Non-Goals

- Hosted/cloud OCR.
- Handwriting recognition.
- Guaranteed perfect formulas, tables, claims, or chemical nomenclature recognition.
- Image-to-chemical-structure recognition.
- Full layout reconstruction beyond page-level text and basic line ordering.
- OCR for arbitrary image collections outside the document-ingestion path.
- Making PaddleOCR, Marker, Surya, or olmOCR required MVP dependencies.

## Acceptance Criteria

- A `needs_ocr` PDF can be OCRed locally and returns to an inspectable parsed state with OCR-backed chunks.
- OCR chunks include repository ID, document ID, document version ID, page range, parser/OCR version, source-file hash, page-image hash where available, offsets or line ranges where available, confidence metadata, and warnings.
- Source Viewer shows OCR text next to page thumbnails and clearly labels OCR-derived chunks.
- Low-confidence pages remain visible and are not silently treated as high-quality parsed text.
- OCR failures are visible, recoverable, and do not delete the original source or previous parse artifacts.
- OCR can be rerun after settings changes without re-uploading the document.
- OCR remains local-first and does not require network access.
- Golden corpus smoke tests verify the OCR stress fixture produces page images, OCR status metadata, and at least one inspectable OCR artifact when OCR dependencies are available.
- OCR output can be disabled, rerun, or discarded without deleting PRD3 page thumbnails or the original parser output.

## Implementation Decisions

- Treat OCR as a derived parse layer, not as a replacement for the original source file.
- Store OCR artifacts separately from page images so page rendering, OCR text, and chunks can be audited independently.
- Keep OCR provider details behind a small adapter interface so the first engine can be replaced or augmented later.
- Record both parser version and OCR provider/version in metadata because scanned PDFs pass through rendering and recognition steps.
- Treat OCRmyPDF plus Tesseract as the baseline provider for the first implementation, and RapidOCR as an optional fallback provider.
- Prefer `pypdfium2` for OCR page rendering so rendering is local, explicit, and separated from text extraction.
- Gate OCR execution through repository settings and explicit user action first; automatic OCR can be added later after performance is understood.
- Use existing document reprocess semantics where possible, but preserve a clear distinction between parser reprocess and OCR reprocess.
- Keep OCR output page-aware before chunking so chat citations can refer back to a page thumbnail.
- Treat pdfplumber as complementary to OCR, not an OCR provider. It may improve layout/table/image metadata for machine-generated PDFs before OCR exists, but scanned-page recovery still belongs to the OCR adapter path.
- Do not accept OCR output into retrieval solely because a text layer exists. Score text quality with character count, word count, unusual-character ratio, whitespace quality, repeated glyph artifacts, and confidence where available.

## Testing Decisions

- Unit test OCR adapter result normalization with synthetic page-image outputs.
- Unit test confidence threshold behavior, warning propagation, and chunk metadata.
- Unit test page routing between native/pdfplumber extraction, OCR rendering, Tesseract baseline OCR, and RapidOCR fallback decisions.
- Integration test upload of a low-text PDF, OCR action, inspect response, and page/OCR artifact retrieval.
- Integration test OCR dependency missing path returns a visible recoverable warning rather than failing ingestion.
- Golden corpus tests should be optional or marked when they require installed OCR binaries.
- Tests should assert external document status, artifacts, warnings, and provenance fields rather than OCR engine internals.
- Add dependency-available smoke tests for OCRmyPDF/Tesseract and RapidOCR fallback, but keep core CI green when optional OCR providers are missing or disabled.

## Out of Scope

PRD13 does not implement full OCR quality evaluation, human correction workflows, or model-based document understanding. It only closes the PRD3 gap where image-only documents are inspectable but not searchable.

## Further Notes

Start with page routing, `pypdfium2` rendering, OCRmyPDF/Tesseract baseline OCR, and one end-to-end UI path for `needs_ocr` documents. Once that is stable, add RapidOCR fallback, language settings, larger golden corpus runs, and retrieval evaluation against scanned patent and scientific fixtures. Keep PaddleOCR, Marker, Surya, and olmOCR as benchmark/evaluation tools until the simple local stack is proven.
