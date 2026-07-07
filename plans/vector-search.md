# Plan: Vector Search with Qdrant

> Source PRD: `prds/05-vector-search-qdrant.md`

## Architectural decisions

Durable decisions that apply across all phases:

- **Routes**: add vector endpoints under `/repositories/{repository_id}/vector`, mirroring the existing full-text rebuild/search workflow.
- **Index lifecycle**: PRD5 keeps one latest vector index per repository. Rebuild replaces the latest index for the repository/settings instead of creating multiple immutable user-visible indexes.
- **Recreate posture**: before rebuild, the user can export the repository manifest so old embedding/vector settings can be recreated later.
- **Future immutable indexes**: multiple retained embedding runs and immutable collections are deferred to a future PRD.
- **Schema**: store an embedding run record in SQLite with repository ID, provider, model, vector size, distance, collection name, status, chunk count, settings snapshot, and timestamps.
- **Vector store**: Qdrant runs in Docker/server mode and stores one active collection per repository embedding run.
- **Embeddings**: PRD5 delivers `sentence-transformers/all-MiniLM-L6-v2` first. `all-mpnet-base-v2`, Ollama embeddings such as `embeddinggemma`, and custom/fine-tuned embeddings are deferred.
- **Filters**: vector search supports the same metadata filters currently exposed for full-text search: document, section, source type, document kind, tag, table/figure hints, and patent section.
- **Testing posture**: normal CI uses deterministic fake embeddings for fast, stable coverage. Real SentenceTransformers and Qdrant coverage is limited to a small integration/e2e test path, with live/local service tests behind the existing `live` marker unless CI is explicitly configured to run Qdrant.

### CI tradeoffs

Using deterministic fake embeddings for most CI keeps tests fast, reliable, offline-friendly, and easier to debug. The main drawbacks are:

- Fake embeddings can hide real model behavior, including vector dimension mismatches, tokenization quirks, slow model startup, and semantically weak retrieval.
- Fake coverage can pass while the real SentenceTransformers dependency, model download/cache path, or Qdrant client version is broken.
- A single real-stack CI test adds confidence, but it increases runtime, cache size, service orchestration complexity, and potential flakiness from model downloads or container startup.
- Real semantic recall assertions are harder to make stable across model/library changes, so the real-stack test should verify plumbing and a tiny expected retrieval path rather than overfitting detailed scores.

---

## Phase 1: Vector Infrastructure Smoke Path

**User stories**: maintainer can run Qdrant locally; missing Qdrant produces a clear setup error.

### What to build

Add the Qdrant client boundary, repository-aware collection naming, and setup/health behavior needed for vector indexing and search. The backend should distinguish missing repository errors from missing Qdrant setup errors.

### Acceptance criteria

- [ ] Qdrant client configuration uses repository settings and app settings.
- [ ] Missing or unreachable Qdrant returns a clear setup error from vector workflows.
- [ ] Collection naming is deterministic for the latest repository vector index.
- [ ] Existing Qdrant Docker setup is documented as the supported server-mode path.

---

## Phase 2: Embedding Settings And Latest Run Records

**User stories**: researcher can see embedding model and vector index settings used for each result.

### What to build

Persist the latest embedding/index run metadata for a repository. A rebuild should supersede the previous latest run while keeping the repository manifest as the way to preserve old settings before replacement.

### Acceptance criteria

- [ ] SQLite stores embedding run metadata for repository, provider, model, vector size, distance, collection, status, chunk count, settings snapshot, and timestamps.
- [ ] Repository manifests include enough embedding/vector settings to recreate an old index after export.
- [ ] Settings validation accepts the PRD5 MiniLM path and rejects incompatible vector settings with actionable errors.
- [ ] Unit tests cover embedding/vector settings validation and run-record shape.

---

## Phase 3: Index A Tiny Corpus End To End

**User stories**: researcher can retrieve conceptually similar chunks from local chunks.

### What to build

Implement local SentenceTransformers embedding for MiniLM and rebuild the latest Qdrant collection from existing document chunks. The first complete path should index a tiny corpus, attach citation-ready chunk payloads, and report the rebuild result.

### Acceptance criteria

- [ ] Rebuild embeds all eligible chunks in a repository with MiniLM.
- [ ] Rebuild replaces the latest repository vector collection.
- [ ] Qdrant payloads include chunk ID, repository ID, document ID, document version ID, chunk index, title, section, page/line provenance, and filterable metadata.
- [ ] Rebuild response reports repository ID, embedding run ID, model, collection, indexed chunk count, and vector settings.
- [ ] Deterministic fake embeddings cover ordinary CI indexing behavior.

---

## Phase 4: Vector Search API

**User stories**: researcher retrieves conceptually similar chunks; results include score/distance, provenance, and embedding run ID.

### What to build

Expose vector search over the latest repository index. The response should feel familiar beside the full-text API while making dense retrieval details explicit.

### Acceptance criteria

- [ ] `POST /repositories/{repository_id}/vector/rebuild` rebuilds the latest vector index.
- [ ] `POST /repositories/{repository_id}/vector/search` searches the latest vector index.
- [ ] Search supports the same filters as current full-text search.
- [ ] Results include rank, dense score/distance, repository ID, document ID, document version ID, chunk ID, chunk index, document title, page/section/line provenance, metadata, embedding run ID, embedding model, vector size, distance, and collection name.
- [ ] Missing repository, missing index, and missing Qdrant cases return distinct clear errors.

---

## Phase 5: Search Lab Vector Mode

**User stories**: researcher can run vector search and inspect settings/results.

### What to build

Enable Vector mode in Search Lab using the same query and filter controls already available for full-text search. Render dense scores and embedding/index settings without changing source-viewer navigation.

### Acceptance criteria

- [ ] Vector mode is selectable in Search Lab.
- [ ] Search Lab can rebuild the vector index and run vector queries.
- [ ] Existing filters work for vector search.
- [ ] Results render dense score/distance, embedding model, collection/run metadata, snippets or chunk text preview, and citation provenance.
- [ ] Opening a vector result navigates to the source viewer at the matched chunk.

---

## Phase 6: Persistence And Evaluation Gates

**User stories**: maintainer can trust index persistence; researcher can verify semantic/paraphrased recall.

### What to build

Add verification that the vector path works in normal deterministic CI, with a minimal real-stack path for confidence when Qdrant and model dependencies are available.

### Acceptance criteria

- [ ] Integration tests index and search a tiny corpus with deterministic fake embeddings in ordinary CI.
- [ ] A small real SentenceTransformers/Qdrant integration or e2e test is available when CI/local services are configured for it.
- [ ] A `live` persistence test confirms Qdrant data survives backend restart or client recreation.
- [ ] Semantic/paraphrase evaluation records recall for a committed fixture set.
- [ ] Test docs describe which checks are deterministic, which require Qdrant, and which require real model downloads.

---

## Phase 7: Ready For Review

**User stories**: maintainer can set up, verify, and review PRD5.

### What to build

Update project docs and run the relevant quality gates before merging.

### Acceptance criteria

- [ ] README and backend/frontend docs describe Qdrant startup, MiniLM embedding setup, vector rebuild/search usage, and troubleshooting.
- [ ] PRD/backlog docs show PRD5 as implemented or ready for review, not complete until accepted.
- [ ] Backend lint, typecheck, and tests pass.
- [ ] Frontend build and tests pass after Search Lab changes.
- [ ] PRD5 acceptance criteria have been checked against local behavior before merge.
