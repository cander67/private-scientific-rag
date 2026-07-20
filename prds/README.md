# PRD Backlog

This folder breaks the local multimodal scientific RAG plan into development-sized PRDs.

Current status:

- Complete: PRD1 local project foundation.
- Complete: PRD2 repository settings and reproducibility.
- Complete: PRD3 document ingestion and source inspection.
- Complete: PRD4 full-text search.
- Complete: PRD5 vector search with Qdrant.
- Complete: PRD6 hybrid search and reranking.
- Complete: PRD7 local RAG chat with citations.
- Complete: PRD8 prompt sandbox.
- Complete: PRD9 export, import, and recreate repository.
- Backlog: PRD10 structured scientific and multimodal parsing.
- Backlog: PRD11 chemistry and patent extensions.
- Backlog: PRD12 bulk patent data integration.
- Backlog: PRD13 parser selection, OCR, and page-image text recovery.
- Backlog: PRD14 structured table extraction.
- Complete: PRD15 additional embedding models.
- Backlog: PRD16 immutable embedding indexes.
- Backlog: PRD17 search metadata quality and result labeling.
- Backlog: PRD18 golden evaluation and evidence-backed promotion.
- Complete: PRD19 repository administration and local reset.
- Complete: PRD20 repository dashboard and home alias.
- Complete: PRD21 settings and model manager.
- Complete: PRD22 Ollama chat model expansion.
- Ready for final review: PRD23 settings model catalog and collection guardrails, including user-testing remediation for model/runtime readiness, Windows Ollama embedding compatibility, Chat Workspace embedding visibility, and docs feedback.
- Backlog: PRD24 local storage provenance and housekeeping.
- Backlog: PRD25 chat context inspection.
- Ready for review: PRD26 repository loading and parser controls.

PRD23 is ready for final review after catalog guardrails and user-testing remediation. The implementation plan is fully checked off locally, deterministic backend/frontend gates passed, and optional live Ollama/Qdrant/GPU checks remain explicit manual checks. PRD26 is ready for review with repository-switch loading states and catalog-backed parser controls; operational parser routing during upload/reprocess and stale parser/chunk index freshness are assigned to PRD13. PRD25 remains backlog follow-up work.

The remaining backlog should be prioritized from hands-on use of the current app, adjusting order when a later PRD is needed to unblock an earlier one.

Shared decisions:

- Frontend: React/Vite.
- Backend: FastAPI.
- Database: SQLite with SQLAlchemy models and Alembic migrations.
- Full-text search: SQLite FTS5.
- Vector store: Qdrant in Docker/server mode.
- Local LLM runtime: Ollama.
- Embeddings: SentenceTransformers first, with room for Ollama embeddings and fine-tuned models later.
- Reranking: cross-encoder default.
- Supported local hosts: macOS, Windows-native Python/Ollama, and Linux/Ubuntu.
- Public repo posture: no secrets, no private data, no generated indexes, no model files, and no restricted document corpus in Git.
- Patent scope: PRD3 supports user-uploaded patent PDFs. Bulk downloads, raw patent feeds, and cross-jurisdiction patent-data normalization are deferred to PRD12.
- Search metadata scope: PRD17 will distinguish chunk-level facts, document-level hints, parser hints, and active filters so Search Lab result labels are trustworthy.
- Evaluation scope: PRD18 owns golden query datasets, retrieval metrics, and evidence-backed promotion to chat defaults. PRD8 stays focused on the researcher-facing Prompt Sandbox.
- Test fixture posture: default CI uses `tests/fixtures/`, not `documents/golden_corpus/`.
- Ollama embedding scope: PRD15 should add one generic Ollama embedding provider plus registry metadata for known supported embedding models. New Ollama embedding models should usually be registry/settings additions when they support Ollama embeddings and pass readiness/vector-dimension checks; they should not require one-off provider code.
- Ollama chat scope: ordinary Ollama chat models should flow through the existing generic chat provider by model name. PRD22 tracks registry/readiness/docs expansion for additional chat models; focused model-specific work is only expected for unusual prompting, context, multimodal, tool/function, or structured-output requirements.
- Chat context inspection scope: PRD25 owns exposing the exact local LLM payload for normal chat. Prompt Sandbox remains the owner for side-by-side prompt/retrieval/model experiments.
- Repository loading and parser controls scope: PRD26 owns visible repository-switch loading states and fixed parser-choice controls, including an `Auto` parser option. PRD13 owns making those parser choices operational during upload, reprocess, OCR, and index freshness checks.

PRD files:

1. [Local project foundation](01-local-project-foundation.md) - complete
2. [Repository settings and reproducibility](02-repository-settings-reproducibility.md) - complete
3. [Document ingestion and source inspection](03-document-ingestion-source-inspection.md) - complete
4. [Full-text search](04-full-text-search.md) - complete
5. [Vector search with Qdrant](05-vector-search-qdrant.md) - complete
6. [Hybrid search and reranking](06-hybrid-search-reranking.md) - complete
7. [Local RAG chat with citations](07-local-rag-chat-citations.md) - complete
8. [Prompt sandbox](08-prompt-sandbox-evaluation.md) - complete
9. [Export, import, and recreate repository](09-export-import-recreate.md) - complete
10. [Structured scientific and multimodal parsing](10-structured-scientific-multimodal-parsing.md) - backlog
11. [Chemistry and patent extensions](11-chemistry-patent-extensions.md) - backlog
12. [Bulk patent data integration](12-bulk-patent-data-integration.md) - backlog
13. [Parser selection, OCR, and page-image text recovery](13-ocr-page-image-text-recovery.md) - backlog
14. [Structured table extraction](14-structured-table-extraction.md) - backlog
15. [Additional embedding models](15-additional-embedding-models.md) - complete
16. [Immutable embedding indexes](16-immutable-embedding-indexes.md) - backlog
17. [Search metadata quality and result labeling](17-search-metadata-quality-result-labeling.md) - backlog
18. [Golden evaluation and evidence-backed promotion](18-golden-evaluation-evidence-promotion.md) - backlog
19. [Repository administration and local reset](19-repository-admin-reset.md) - complete
20. [Repository dashboard and home alias](20-repository-dashboard-home.md) - complete
21. [Settings and model manager](21-settings-models-manager.md) - complete
22. [Ollama chat model expansion](22-ollama-chat-model-expansion.md) - complete
23. [Settings model catalog and collection guardrails](23-settings-model-catalog-guardrails.md) - ready for final review
24. [Local storage provenance and housekeeping](24-local-storage-housekeeping.md) - backlog
25. [Chat context inspection](25-chat-context-inspection.md) - backlog
26. [Repository loading and parser controls](26-repository-loading-and-parser-controls.md) - ready for review
