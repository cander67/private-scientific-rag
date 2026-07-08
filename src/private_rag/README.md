# Backend Package

The backend package contains the FastAPI app, configuration, database wiring, repository metadata, document ingestion/source inspection, full-text search, vector search, and future hybrid retrieval/reranking/RAG services.

Module boundaries:

- `api/`: FastAPI application and routes.
- `core/`: settings and shared application infrastructure.
- `db/`: SQLAlchemy base, engine, and session wiring.
- `repositories/`: repository SQLAlchemy models, Pydantic settings/manifest schemas, and reproducibility service logic.
- `search/`: SQLite FTS5 schema management, sparse index rebuilds, query normalization, field weighting, result shaping, and exact-match recall evaluation.
- `vector/`: embedding provider boundary, Qdrant vector-store boundary, latest embedding-run metadata, vector index rebuild/search orchestration, and semantic recall evaluation.
- `retrieval/`: unified retrieval request/response schemas, retrieval run/result persistence, and orchestration across full-text, vector, hybrid, and reranked search modes.
- `services/`: local service checks and future domain services.
- `ingestion/`: document upload models, PDF parser fallback chain, parser/chunker service, source file storage, and provenance schemas.
- Ingestion keeps original source files, parsed artifacts, chunks, and provenance metadata distinct.

Current API surface:

- `GET /health`: local app and dependency health check.
- `GET /repositories/default`: creates or returns the default repository with validated settings.
- `GET /repositories/{repository_id}/settings`: loads repository settings.
- `PUT /repositories/{repository_id}/settings`: validates and saves repository settings.
- `GET /repositories/{repository_id}/manifest`: exports a reproducibility manifest and stores a snapshot.
- `POST /repositories/recreate/validate`: reports missing source files, missing models, and incompatible settings before recreate work begins.
- `POST /repositories/{repository_id}/documents`: uploads and parses a local document.
- `GET /repositories/{repository_id}/documents`: lists uploaded documents.
- `GET /repositories/{repository_id}/documents/{document_id}`: inspects parsed chunks and provenance.
- `GET /repositories/{repository_id}/documents/{document_id}/versions/{version_id}/page-images/{page}`: serves generated PDF page thumbnails for source inspection.
- `POST /repositories/{repository_id}/documents/{document_id}/reprocess`: reparses the stored source file.
- `DELETE /repositories/{repository_id}/documents/{document_id}`: deletes a document and derived chunks.
- `POST /repositories/{repository_id}/full-text/rebuild`: rebuilds the SQLite FTS5 sparse index for one repository.
- `POST /repositories/{repository_id}/full-text/search`: searches indexed chunks and returns BM25 score, snippet, matched fields, metadata filters, document/chunk metadata, and citation-ready provenance.
- `POST /repositories/{repository_id}/vector/rebuild`: replaces the latest Qdrant vector index for one repository using the configured embedding model.
- `POST /repositories/{repository_id}/vector/search`: searches the latest vector index and returns dense score, embedding run/model/index settings, metadata filters, document/chunk metadata, and citation-ready provenance.
- `POST /repositories/{repository_id}/retrieval/search`: searches through the unified retrieval contract. Full-text, vector, and hybrid modes are available, with candidate-pool size, adjustable RRF constant, reranker strategy, metadata boost settings, normalized score breakdowns, and max-five recent retrieval run/result persistence. Reranking is being added in follow-up PRD6 slices.

Current status:

- PRD1 foundation is complete.
- PRD2 repository-aware settings and reproducibility are complete.
- PRD3 local document ingestion and source inspection are complete.
- PRD4 full-text search is complete: sparse index rebuild, full-text query API, metadata filters, exact-match evaluation, and frontend Search Lab are available.
- PRD5 vector search with Qdrant is complete and closed: latest-index rebuild, vector query API, metadata filters, embedding run metadata, deterministic CI tests, semantic recall evaluation, and frontend Search Lab vector mode are available.
- PRD6 hybrid search and reranking is in progress: unified retrieval search, retrieval run/result persistence, five-history retention, hybrid orchestration, and Reciprocal Rank Fusion are available; selectable reranking, evaluation, and Search Lab controls are next.

PDF parsing tries `pypdf`, then PyMuPDF, gates image-only/no-native-text pages as `needs_ocr`, then uses Docling and a conservative built-in fallback for remaining non-image PDFs. PRD3 intentionally does not run a full OCR pipeline; PRD13 owns OCRmyPDF/Tesseract and fallback OCR. Bulk patent-data feeds and multi-jurisdiction patent parsing are deferred to PRD12.
