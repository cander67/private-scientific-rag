# PRD 5: Vector Search with Qdrant

## Goal

Implement persistent dense vector search using Qdrant server mode and local embeddings.

## User Stories

- As a researcher, I can retrieve conceptually similar chunks even when the query wording differs from the source.
- As a maintainer, I can run Qdrant locally through Docker/server mode.
- As a researcher, I can see embedding model and vector index settings used for each result.

## Scope

- Qdrant Docker Compose service.
- Qdrant client configuration.
- Vector store interface.
- Embedding service using SentenceTransformers first.
- Initial models: `all-MiniLM-L6-v2` and `all-mpnet-base-v2`.
- Embedding run records.
- Vector search API.
- Vector result display in Search Lab.

## Future Options

- Ollama embedding models such as `embeddinggemma:300m`.
- Larger embedding models such as `qwen3-embedding:8b`.
- Custom fine-tuned scientific/patent embedding models.

## Acceptance Criteria

- Qdrant collection is created per repository/embedding run.
- Vector index survives backend restart.
- Vector results include score/distance, chunk metadata, repository ID, document ID, page/section data, and embedding run ID.
- Missing Qdrant service produces a clear setup error.
- Embedding settings are included in repository snapshots and manifests.

## Test Plan

- Unit test embedding settings validation.
- Integration test indexing and vector search with a tiny corpus.
- Restart test confirms persistent Qdrant data.
- Evaluation records recall for semantic/paraphrased queries.

## Documentation References

- Qdrant documentation: https://qdrant.tech/documentation/overview/
- Qdrant GitHub repository: https://github.com/qdrant/qdrant
- SentenceTransformers documentation: https://sbert.net/
- Azure vector search overview: https://learn.microsoft.com/en-us/azure/search/vector-search-overview
