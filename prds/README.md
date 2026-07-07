# PRD Backlog

This folder breaks the local multimodal scientific RAG plan into development-sized PRDs.

Current status:

- Complete: PRD1 local project foundation.
- Complete: PRD2 repository settings and reproducibility.
- Complete: PRD3 document ingestion and source inspection.
- Complete: PRD4 full-text search.
- Ready for review: PRD5 vector search with Qdrant.

The intended flow is:

1. Approve all static HTML mockups.
2. Initialize and publish the public GitHub repository with a clean first commit.
3. Open implementation PRs against these PRDs in order, adjusting order only when a later PRD is needed to unblock an earlier one.

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
- Test fixture posture: default CI uses `tests/fixtures/`, not `documents/golden_corpus/`.

PRD files:

1. [Local project foundation](01-local-project-foundation.md) - complete
2. [Repository settings and reproducibility](02-repository-settings-reproducibility.md) - complete
3. [Document ingestion and source inspection](03-document-ingestion-source-inspection.md) - complete
4. [Full-text search](04-full-text-search.md) - complete
5. [Vector search with Qdrant](05-vector-search-qdrant.md) - ready for review
6. [Hybrid search and reranking](06-hybrid-search-reranking.md)
7. [Local RAG chat with citations](07-local-rag-chat-citations.md)
8. [Prompt sandbox and evaluation](08-prompt-sandbox-evaluation.md)
9. [Export, import, and recreate repository](09-export-import-recreate.md)
10. [Structured scientific and multimodal parsing](10-structured-scientific-multimodal-parsing.md)
11. [Chemistry and patent extensions](11-chemistry-patent-extensions.md)
12. [Bulk patent data integration](12-bulk-patent-data-integration.md)
13. [OCR and page-image text recovery](13-ocr-page-image-text-recovery.md)
14. [Structured table extraction](14-structured-table-extraction.md)
15. [Additional embedding models](15-additional-embedding-models.md)
16. [Immutable embedding indexes](16-immutable-embedding-indexes.md)
