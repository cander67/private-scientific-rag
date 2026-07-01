# PRD 3: Document Ingestion and Source Inspection

## Problem Statement

Researchers need to upload a small, trusted set of local research documents and inspect exactly how the RAG system parsed them before those documents are indexed or used for answers. The first ingestion milestone must handle scientific PDFs, text files, markdown files, annotation sidecars, and user-uploaded patent PDFs of interest, while deferring automated patent bulk downloads and raw patent-data formats to a later PRD.

## Solution

Build repository-scoped document ingestion for locally selected files, structured parsing, chunking with provenance, and a Source Viewer that exposes parsed pages, sections, chunks, tables, figures, warnings, and patent PDF sections. Treat patents in this PRD as uploaded PDFs only. The parser should recognize patent-like structure when present, but it should not fetch, normalize, or parse raw patent feeds from USPTO, EPO, WIPO, JPO, or other jurisdictions.

The initial rollout follows the first-pass sequence in `documents/golden_corpus/golden_corpus_manifest_v1.md`:

1. Ingest the four existing local PDFs: `US9941441.pdf`, `US11370944.pdf`, `US11845885.pdf`, and `ol401035t_si_001.pdf`.
2. Add three web PDFs: arXiv `2111.01037` as `sectioned-paper.pdf`, arXiv `1806.03173` as `table-heavy.pdf`, and arXiv `1704.06526` as `figure-caption.pdf`.
3. Add three non-PDF files: an Olivetti `.txt` sample, its matching `.ann` file, and the Olivetti `README.md`.
4. Run ingestion and manually inspect page counts, section maps, table/caption candidates, OCR flags, chunk metadata, and citation-card rendering.
5. Add arXiv source bundles only after PDF/text/markdown ingestion is stable.

## User Stories

1. As a researcher, I can upload PDFs, TXT, Markdown, and ANN files into a repository, so that my local corpus can be parsed without relying on external hosting.
2. As a researcher, I can upload PDF copies of patents I already care about, so that patent claims, abstracts, drawings, examples, and descriptions can be searched later.
3. As a researcher, I can see whether each file was uploaded, parsed, chunked, embedded, failed, skipped, or marked as needing OCR, so that I know what happened before trusting results.
4. As a researcher, I can inspect parsed pages, sections, chunks, tables, figures, captions, claims, examples, and parsing warnings, so that I can validate source provenance.
5. As a researcher, I can see page thumbnails for image-heavy or image-only PDFs, so that important patent drawings or scientific figures are not hidden when text extraction is sparse.
6. As a researcher, I can reprocess a document after changing parser settings, so that parser improvements can be applied without re-uploading everything.
7. As a researcher, I can delete a document and its derived parse artifacts, so that private or irrelevant material can be removed from a repository.
8. As a researcher, I can inspect line-based provenance for text and markdown files, so that non-PDF citations are still auditable.
9. As a researcher, I can keep `.ann` annotations linked to their paired `.txt` file, so that scientific annotations remain useful without becoming detached prose.

## Scope

- Upload API for repository-scoped local files.
- Source file storage by repository and document version.
- File hashing and duplicate detection.
- Structured PDF parser integration from the start, with `pypdf` fallback.
- Page-aware, section-aware parsed document model.
- Patent-PDF section hints for front matter, abstract, description, examples, claims, drawing sheets, and classifications when detectable.
- Text, markdown, and BRAT `.ann` ingestion sufficient for the golden corpus.
- Chunking service that records page, section, line, parser, and offset provenance where available.
- Source Viewer UI for parsed text, page thumbnails, chunks, warnings, and provenance.
- OCR-needed detection and visible status, without requiring full OCR implementation in this PRD.
- Golden corpus fixtures and checks that match the revised corpus structure.

## Non-Goals

- Automated patent search, patent family expansion, or bulk patent downloading.
- Raw patent XML, SGML, APS, TIFF, ZIP, or jurisdiction-specific patent feed parsing.
- Patent data normalization across USPTO, EPO, WIPO, JPO, KIPO, CNIPA, or other offices.
- Perfect table extraction.
- Full OCR pipeline.
- Chemistry entity extraction.
- Vector or full-text indexing beyond storing chunk-ready outputs.
- Production-grade license compliance automation for third-party test files.

## Acceptance Criteria

- Upload supports PDF, TXT, Markdown, and ANN files.
- User-uploaded patent PDFs are accepted as normal PDF documents and can expose patent-like section hints when parsing supports them.
- Duplicate unchanged files are skipped or versioned according to repository settings.
- Parsed PDF outputs preserve page and section metadata.
- Text and markdown outputs preserve heading or line-range provenance.
- `.ann` files can be associated with paired `.txt` files by base filename.
- Chunks include repository ID, document ID, document version ID, page range or line range, section, chunk index, parser version, offsets where available, and source-file hash.
- Image-only or low-text PDFs are marked as `needs_ocr` or equivalent instead of silently disappearing.
- Parsing failures are visible and recoverable.
- Source Viewer shows parsed text, page thumbnails for PDFs, chunk provenance, parser warnings, and patent-PDF section hints where available.
- The first-pass golden corpus can be ingested in the rollout order above and manually inspected.

## Implementation Decisions

- Ingestion is repository-scoped and builds on the PRD2 repository settings model rather than creating parallel configuration.
- Document storage distinguishes original source files from derived parse artifacts, chunks, page images, and inspection metadata.
- Parser results use a stable intermediate model that can later feed full-text search, vector search, hybrid retrieval, chat citations, and exports.
- Patent support in this PRD is PDF-first: parse what the uploaded PDF contains, capture useful section hints, and defer jurisdictional source APIs.
- `.ann` files are related assets, not standalone prose documents by default.
- OCR is represented as status and metadata first; full OCR execution can be implemented later without changing upload semantics.

## Testing Decisions

- Unit test file hashing, duplicate detection, source-type detection, and chunk boundary behavior.
- Unit test `.txt` and `.ann` pairing by filename and stable offsets.
- Integration test upload -> parse -> chunk -> inspect for PDF, TXT, Markdown, ANN, and patent PDF fixtures.
- Golden corpus smoke tests should use `documents/golden_corpus/checks/expected_features.yaml` and `documents/golden_corpus/checks/retrieval_questions.md` once those fixtures are populated.
- Tests should assert external behavior and provenance fields rather than parser-internal implementation details.

## Documentation References

- `documents/golden_corpus/golden_corpus_manifest_v1.md` for corpus layout, rollout order, expected features, and smoke-test questions.
- `tests/README.md` for golden corpus test conventions.
- `src/private_rag/README.md` for backend module boundaries.
- FastAPI file upload documentation: https://fastapi.tiangolo.com/tutorial/request-files/
- Docling documentation: https://docling-project.github.io/docling/
- pypdf documentation: https://pypdf.readthedocs.io/
