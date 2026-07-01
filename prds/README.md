# PRD Backlog

This folder breaks the local multimodal scientific RAG plan into development-sized PRDs.

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

PRD files:

1. [Local project foundation](01-local-project-foundation.md)
2. [Repository settings and reproducibility](02-repository-settings-reproducibility.md)
3. [Document ingestion and source inspection](03-document-ingestion-source-inspection.md)
4. [Full-text search](04-full-text-search.md)
5. [Vector search with Qdrant](05-vector-search-qdrant.md)
6. [Hybrid search and reranking](06-hybrid-search-reranking.md)
7. [Local RAG chat with citations](07-local-rag-chat-citations.md)
8. [Prompt sandbox and evaluation](08-prompt-sandbox-evaluation.md)
9. [Export, import, and recreate repository](09-export-import-recreate.md)
10. [Structured scientific and multimodal parsing](10-structured-scientific-multimodal-parsing.md)
11. [Chemistry and patent extensions](11-chemistry-patent-extensions.md)
12. [Bulk patent data integration](12-bulk-patent-data-integration.md)
