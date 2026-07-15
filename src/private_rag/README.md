# Backend Package

The backend package contains the FastAPI app, configuration, database wiring, repository metadata, document ingestion/source inspection, full-text search, vector search, hybrid retrieval/reranking, and future RAG services.

Module boundaries:

- `api/`: FastAPI application and routes.
- `core/`: settings and shared application infrastructure.
- `db/`: SQLAlchemy base, engine, and session wiring.
- `repositories/`: repository SQLAlchemy models, Pydantic settings/manifest schemas, and reproducibility service logic.
- `search/`: SQLite FTS5 schema management, sparse index rebuilds, query normalization, field weighting, result shaping, and exact-match recall evaluation.
- `vector/`: embedding provider boundary, Qdrant vector-store boundary, latest embedding-run metadata, vector index rebuild/search orchestration, and semantic recall evaluation.
- `retrieval/`: unified retrieval request/response schemas, retrieval run/result persistence, and orchestration across full-text, vector, hybrid, and reranked search modes.
- `chat/`: local Ollama chat boundary, model registry, chat session/message persistence, RAG prompt assembly, readiness checks, and citation mapping.
- `exports/`: portable repository ZIP bundle schemas and export assembly.
- `services/`: local service checks and future domain services.
- `ingestion/`: document upload models, PDF parser fallback chain, parser/chunker service, source file storage, and provenance schemas.
- Ingestion keeps original source files, parsed artifacts, chunks, and provenance metadata distinct.

Current API surface:

- `GET /health`: local app and dependency health check.
- `GET /repositories/default`: creates or returns the default repository with validated settings.
- `GET /repositories/{repository_id}/settings`: loads repository settings.
- `PUT /repositories/{repository_id}/settings`: validates and saves repository settings.
- `GET /repositories/{repository_id}/manifest`: exports a reproducibility manifest and stores a snapshot.
- `POST /repositories/{repository_id}/exports/bundle`: exports a portable repository ZIP with manifest, settings, prompt library, document/chunk metadata, chat history, retrieval history, citations, and selected source files. PRD8 sandbox runs/comparisons are excluded by default and included only when explicitly requested.
- `POST /repositories/recreate/bundle/validate`: validates a portable repository ZIP before recreate, including manifest/payload consistency, source hashes, external source mappings, model availability reports, parser fingerprints, and exported count summaries.
- `POST /repositories/recreate/bundle`: recreates a repository from a validated portable ZIP, preferring a new repository while allowing explicit restore into an empty target repository, then reparses sources, restores active chat/retrieval history, rebuilds SQLite FTS5 and Qdrant indexes, and returns a recreate report.
- `POST /repositories/recreate/validate`: reports missing source files, missing models, and incompatible settings before recreate work begins.
- `POST /repositories/{repository_id}/documents`: uploads and parses a local document.
- `GET /repositories/{repository_id}/documents`: lists uploaded documents.
- `GET /repositories/{repository_id}/documents/{document_id}`: inspects parsed chunks and provenance.
- `GET /repositories/{repository_id}/documents/{document_id}/versions/{version_id}/page-images/{page}`: serves generated PDF page thumbnails for source inspection.
- `POST /repositories/{repository_id}/documents/{document_id}/reprocess`: reparses the stored source file.
- `DELETE /repositories/{repository_id}/documents/{document_id}`: deletes a document and derived chunks.
- `DELETE /repositories/{repository_id}/documents`: deletes all documents and derived chunks for one repository.
- `POST /repositories/{repository_id}/full-text/rebuild`: rebuilds the SQLite FTS5 sparse index for one repository.
- `POST /repositories/{repository_id}/full-text/search`: searches indexed chunks and returns BM25 score, snippet, matched fields, metadata filters, document/chunk metadata, and citation-ready provenance.
- `POST /repositories/{repository_id}/vector/rebuild`: replaces the latest Qdrant vector index for one repository using the configured embedding model.
- `POST /repositories/{repository_id}/vector/search`: searches the latest vector index and returns dense score, embedding run/model/index settings, metadata filters, document/chunk metadata, and citation-ready provenance.
- `POST /repositories/{repository_id}/retrieval/search`: searches through the unified retrieval contract. Full-text, vector, and hybrid modes are available, with a default candidate pool of `top_k * 5`, adjustable RRF constant defaulting to `60`, selectable reranker strategy, cross-encoder score contribution, High/Medium/Low metadata boost settings, normalized score breakdowns, and max-five recent retrieval run/result persistence.
- `GET /repositories/{repository_id}/chat/models`: lists local chat model registry entries and the default model.
- `POST /repositories/{repository_id}/chat/models/smoke`: checks that the configured local Ollama model can respond.
- `GET /repositories/{repository_id}/chat/readiness`: reports full-text index, vector index, and local model readiness for chat.
- `GET /repositories/{repository_id}/chat/sessions`: lists repository chat sessions.
- `POST /repositories/{repository_id}/chat/sessions`: creates a repository chat session with chat-owned retrieval settings.
- `GET /repositories/{repository_id}/chat/sessions/{chat_session_id}`: loads persisted chat messages and citation metadata.
- `POST /repositories/{repository_id}/chat/sessions/{chat_session_id}/messages`: asks a repository-grounded question using the session/request retrieval settings and persists the user/assistant messages.
- `DELETE /repositories/{repository_id}/chat/sessions/{chat_session_id}`: deletes one chat session.
- `DELETE /repositories/{repository_id}/chat/sessions`: clears repository chat sessions.

Current status:

- PRD1 foundation is complete.
- PRD2 repository-aware settings and reproducibility are complete.
- PRD3 local document ingestion and source inspection are complete.
- PRD4 full-text search is complete: sparse index rebuild, full-text query API, metadata filters, exact-match evaluation, and frontend Search Lab are available.
- PRD5 vector search with Qdrant is complete: latest-index rebuild, vector query API, metadata filters, embedding run metadata, deterministic CI tests, semantic recall evaluation, and frontend Search Lab vector mode are available.
- PRD6 hybrid search and reranking is complete: unified retrieval search, retrieval run/result persistence, five-history retention, hybrid orchestration, Reciprocal Rank Fusion, selectable reranking, comparison evaluation, and Search Lab controls are available.
- PRD7 local RAG chat with citations is complete and closed: Ollama chat boundary, model registry, readiness checks, chat session persistence, prompt library settings, chat-owned retrieval controls, citation mapping, and Chat Workspace are available.
- PRD8 Prompt Sandbox is complete and closed: repository-scoped sandbox prompt versions, copy-to/from chat prompt library, prompt deletion, persisted sandbox runs, progressive side-by-side retrieval comparisons, local-model generation, retrieved context snapshots, latency/status display, and the Prompt Sandbox workspace are available. Golden evaluation metrics and evidence-backed promotion are deferred to PRD18.
- PRD9 export/import/recreate is complete and closed: portable ZIP export bundles, bundle validation, backend recreate execution, active history restore, full-text/vector index rebuild reporting, Export Center, Recreate Repository, and cross-platform transfer documentation are available.

Repository chat prompts live in repository settings under `prompt.library`, with `prompt.active_chat_prompt_id` selecting the active prompt. The default prompt requires repository-grounded answers, inline citations, and explicit uncertainty when context is insufficient. Chat retrieval settings are stored on each chat session and may be overridden per question; they do not inherit frontend Search Lab state and do not trigger automatic index rebuilds. Readiness is explicit: full-text and vector status compare parsed chunks against indexed chunks, report missing/partial/stale/ready states, and require the selected retrieval mode plus a responding local model before chat is marked ready.

The default cross-encoder is `cross-encoder/ms-marco-MiniLM-L6-v2`. It must be downloaded into the local SentenceTransformers cache before live reranking; a missing model returns setup guidance instead of silently falling back. Diversity/MMR remains a future strategy. Default CI uses deterministic providers, while real Qdrant and cross-encoder checks are explicit opt-in tests documented in `tests/README.md`.

PDF parsing tries `pypdf`, then PyMuPDF, gates image-only/no-native-text pages as `needs_ocr`, then uses Docling and a conservative built-in fallback for remaining non-image PDFs. PRD3 intentionally does not run a full OCR pipeline; PRD13 owns OCRmyPDF/Tesseract and fallback OCR. Bulk patent-data feeds and multi-jurisdiction patent parsing are deferred to PRD12. More precise result-label metadata scoping is deferred to PRD17.
