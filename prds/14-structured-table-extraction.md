# PRD 14: Structured Table Extraction

## Problem Statement

PRD3 and PRD10 recognize that scientific PDFs often contain crucial data in tables, but the current ingestion path only preserves text chunks and lightweight table hints. Researchers need table contents, captions, page provenance, and retrieval citations that point to specific table artifacts instead of flattening everything into nearby prose. Without structured table extraction, materials databases, experimental results, patent examples, and supporting-information tables remain hard to inspect, search, and cite.

## Solution

Add a structured table extraction layer for scientific PDFs and supporting-information documents. The system should detect table candidates, extract table text/cells where available, preserve table captions and page provenance, store table artifacts as derived inspection data, and create table-aware chunks that can participate in retrieval and citations. The first implementation should favor reliable extraction from parser-supported documents and graceful fallback to table hints when full structure is unavailable.

pdfplumber should be included in the native/digital-PDF parsing layer for this PRD, especially while OCR is being prepared. It is local and open source, and it can extract text, words, characters, bounding boxes, lines, rectangles, images, annotations, hyperlinks, and tables from born-digital PDFs. It works best on machine-generated PDFs rather than scanned PDFs, so it should complement `pypdf`, Docling, and PyMuPDF for digital PDFs and defer image-only/scanned tables to PRD13 OCR plus later layout-aware table recognition.

Recommended staged roadmap:

1. PRD3 remains stable: continue accepting PDFs, rendering page thumbnails, storing chunks, and marking low-text PDFs as `needs_ocr`.
2. Add pdfplumber after `pypdf` as the richer digital-PDF extraction path for words, coordinates, layout hints, and tables.
3. Score native/pdfplumber page extraction quality before deciding whether a page needs OCR.
4. Record pdfplumber page objects, table candidates, bounding boxes, and extraction warnings as derived metadata.
5. Compare pdfplumber table candidates with Docling table outputs where both exist, then normalize both into one table artifact model.
6. Render table artifacts in Source Viewer with page-thumbnail context and parser provenance.
7. After PRD13 OCR lands, add an OCR-table path for scanned tables and keep those artifacts clearly labeled as OCR-derived.

## User Stories

1. As a researcher, I can inspect extracted tables from a PDF, so that tabular experimental data is not hidden inside prose chunks.
2. As a researcher, I can see table captions and page numbers, so that I can verify where a table came from.
3. As a researcher, I can search for values, materials, properties, and units inside extracted tables, so that data-heavy papers are retrievable.
4. As a researcher, I can cite a specific table or table row when possible, so that answers are auditable.
5. As a researcher, I can tell when a table was only detected as a hint, so that I do not over-trust incomplete structure.
6. As a maintainer, I can plug in parser-specific table extractors, so that Docling, PyMuPDF, and future parsers can contribute table artifacts without changing the retrieval layer.
7. As a maintainer, I can test table extraction on bounded golden fixtures, so that CI remains fast and deterministic.

## Scope

- Table artifact model with document/version/page provenance, table index, caption, extracted cells, plain-text representation, confidence/quality metadata, parser name/version, and warnings.
- Parser adapter interface for table extraction from available structured parser outputs.
- Initial support for pdfplumber table and page-object extraction for born-digital PDFs.
- Support for Docling table outputs where available, normalized through the same table artifact model.
- Native extraction quality scoring based on character count, word count, unusual-character ratio, whitespace quality, repeated glyph artifacts, and table-like structure.
- Fallback heuristics for text-only table/caption hints when neither structured parser can extract a usable table grid.
- Storage of table artifacts separately from source files, page images, and chunks.
- Table-aware chunks that include table ID, caption, page range, row/column metadata where available, parser version, source hash, and artifact hash.
- Source Viewer table panel showing extracted table preview, caption, page thumbnail context, warnings, and linked chunks.
- Search/retrieval metadata that can filter or boost table-backed chunks in later PRDs.
- Golden corpus coverage for `table-heavy.pdf`, supporting-information tables, and at least one synthetic small table fixture.

## Non-Goals

- Perfect table extraction across every PDF layout.
- Structured extraction from scanned/image-only tables before the OCR roadmap lands.
- Manual spreadsheet editing or table correction UI.
- Full data cleaning, unit normalization, or schema inference.
- Chart/plot data extraction.
- Chemical structure recognition from table images.
- Large-scale table export workflows beyond local inspection data.

## Acceptance Criteria

- At least one golden corpus table-heavy PDF produces inspectable table artifacts when the structured parser supports it.
- Table artifacts include document ID, document version ID, page number or page range, table index, parser name/version, caption where detected, warnings, and source/artifact hashes.
- Table-backed chunks include table provenance and can be distinguished from ordinary text chunks.
- Source Viewer exposes table artifacts and links them to page thumbnails and related chunks.
- When full table extraction fails, the document still preserves table/caption hints and parser warnings.
- Reprocessing a document refreshes table artifacts and table-backed chunks without re-uploading the source file.
- pdfplumber integration does not change PRD3 upload semantics or make table extraction a prerequisite for ordinary PDF parsing.
- Scanned-table extraction is labeled as deferred to PRD13 OCR and later layout-aware recognition.
- Native/pdfplumber extraction quality is visible enough that bad digital text does not silently beat OCR routing later.
- Tests assert external table artifacts, chunks, and provenance fields rather than parser-private data structures.

## Implementation Decisions

- Treat tables as derived artifacts with their own stable IDs rather than burying table data only in chunk metadata.
- Keep parser-specific table extraction behind an adapter boundary so pdfplumber, Docling, and future tools can contribute without locking the system to one parser.
- Add pdfplumber behind the same adapter boundary rather than inserting pdfplumber-specific fields directly into chunks or document versions.
- Use pdfplumber before OCR for born-digital layout/table extraction, not as a replacement for OCR.
- Store both a structured cell representation and a normalized plain-text/table-markdown representation for retrieval.
- Keep table captions and surrounding page text linked but distinct, because citations may need either the table itself or the explanatory prose around it.
- Preserve a fallback path for documents that have table mentions but no extractable cell grid.
- Do not make table extraction a hard dependency for normal PDF ingestion; parser failures should degrade to warnings and ordinary chunks.
- Treat pdfplumber page-level output as useful for chunk provenance even when table extraction is incomplete, because word coordinates and page objects can still improve citation debugging.

## Testing Decisions

- Unit test table artifact normalization from parser-like table payloads into the internal model.
- Unit test pdfplumber adapter normalization for page objects, bounding boxes, extracted tables, warnings, and empty-table outcomes.
- Unit test digital-page quality scoring that decides whether native/pdfplumber output is good enough or should be routed to OCR later.
- Unit test table-backed chunk metadata, artifact hash generation, and fallback warning behavior.
- Integration test upload -> parse -> inspect for a tiny synthetic table PDF or fixture.
- Golden corpus smoke test `table-heavy.pdf` for table detection, captions where available, and Source Viewer metadata.
- Frontend tests should cover table panel rendering, fallback hint rendering, and table-backed provenance labels.
- Tests should avoid asserting exact OCR or parser cell ordering unless using a deterministic synthetic fixture.

## Out of Scope

PRD14 does not replace broader PRD10 multimodal parsing. It is the implementation slice for table artifacts and table-backed retrieval provenance. Figure extraction, OCR, chart digitization, chemistry extraction, and table export workflows remain separate work.

## Further Notes

Start with table artifacts and inspection before adding retrieval ranking behavior. A useful first milestone is: one table-heavy fixture produces an inspectable table artifact, one fallback fixture produces table hints only, and both states are obvious in the Source Viewer.

pdfplumber can be integrated before full OCR because it improves born-digital layout/table inspection without changing the local-first OCR plan. It should affect PRD3 only as an optional parser/artifact enhancement: PRD3 acceptance should remain satisfied without it, digital pages can gain better coordinates and table hints, and image-only PDFs should still move through the `needs_ocr` path.

The longer-term evaluation branch should consider PaddleOCR, Marker, Surya, and olmOCR only after the core table artifact model tracks page number, rendered page image path, text source method, block-level metadata, OCR confidence where applicable, bounding boxes, section/table/figure hints, and chunk provenance.
