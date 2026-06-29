# PRD 6: Hybrid Search and Reranking

## Goal

Combine full-text and vector retrieval with Reciprocal Rank Fusion, then apply selectable reranking strategies.

## User Stories

- As a researcher, I can choose full-text, vector, or hybrid search.
- As a researcher, I can choose a reranking strategy from a menu.
- As a researcher, I can inspect dense score, BM25 score, RRF score, rerank score, and final rank.
- As a developer, I can compare search modes against the golden query set.

## Scope

- Hybrid retrieval orchestration.
- Reciprocal Rank Fusion.
- Reranking strategy interface.
- Cross-encoder reranker default.
- Initial reranker: `cross-encoder/ms-marco-MiniLM-L6-v2`.
- Metadata boost strategy.
- Retrieval run and retrieval result persistence.
- Search Lab UI controls.

## Reranking Menu

- `None`
- `Cross-encoder`
- `Metadata boost`
- `Cross-encoder + metadata boost`
- `Diversity/MMR` as a future option

## Acceptance Criteria

- UI exposes full-text, vector, and hybrid modes.
- UI exposes reranking strategy menu.
- Hybrid search runs full-text and vector retrieval independently and merges by RRF.
- Retrieval runs store all mode, filter, candidate pool, top-k, model, and reranker settings.
- Reranking changes ordering in a controlled test.
- Score breakdown is visible for each result.

## Test Plan

- Unit test RRF merge behavior.
- Unit test reranker strategy selection.
- Integration test hybrid search with and without reranking.
- Evaluation compares full-text, vector, hybrid, and reranked hybrid.

## Documentation References

- Elastic semantic relevance tuning: https://www.elastic.co/search-labs/blog/search-relevance-tuning-in-semantic-search
- Azure hybrid search overview: https://learn.microsoft.com/en-us/azure/search/hybrid-search-overview
- SentenceTransformers CrossEncoder documentation: https://www.sbert.net/docs/package_reference/cross_encoder/model.html
- Cross-encoder baseline: https://huggingface.co/cross-encoder/ms-marco-MiniLM-L6-v2
