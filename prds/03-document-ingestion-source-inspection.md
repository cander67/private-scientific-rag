# PRD 3: Document Ingestion and Source Inspection

## Goal

Let a researcher upload local documents, parse them with structured parsing, chunk them with provenance, and inspect what will be searched.

## User Stories

- As a researcher, I can upload PDFs, TXT, and Markdown files.
- As a researcher, I can see whether a document was uploaded, parsed, chunked, embedded, failed, or skipped.
- As a researcher, I can inspect pages, sections, chunks, tables, figures, and parsing warnings.
- As a researcher, I can reprocess or delete documents.

## Scope

- Upload API.
- Source file storage by repository.
- File hashing and duplicate detection.
- Structured PDF parser integration from the start.
- `pypdf` fallback.
- Page-aware and section-aware parsed document model.
- Chunking service.
- Source Viewer UI.

## Non-Goals

- Perfect table extraction.
- Full OCR pipeline.
- Chemistry entity extraction.
- Vector or full-text indexing beyond storing chunk-ready outputs.

## Acceptance Criteria

- Upload supports PDF, TXT, and Markdown.
- Duplicate unchanged files are skipped or versioned according to settings.
- Parsed outputs preserve page and section metadata.
- Chunks include repository ID, document ID, document version ID, page range, section, chunk index, parser version, and offsets where available.
- Parsing failures are visible and recoverable.
- Source Viewer shows parsed text and chunk provenance.

## Test Plan

- Unit test file hashing.
- Unit test chunk boundaries.
- Integration test upload -> parse -> chunk -> inspect.
- Golden corpus includes sectioned PDF, table PDF, figure-caption PDF, patent-like document, and chemistry-heavy document.

## Documentation References

- `tests/README.md` for golden corpus test conventions.
- `src/private_rag/README.md` for backend module boundaries.
- FastAPI file upload documentation: https://fastapi.tiangolo.com/tutorial/request-files/
- Docling documentation: https://docling-project.github.io/docling/
- pypdf documentation: https://pypdf.readthedocs.io/
