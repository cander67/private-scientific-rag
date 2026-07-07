# PRD 15: Additional Embedding Models

## Goal

Expand vector search beyond the initial MiniLM baseline so researchers can choose stronger or more specialized embedding models when local resources allow, while preserving the local-first Qdrant index lifecycle from PRD5.

This PRD carries forward the PRD5 model roadmap:

- `all-mpnet-base-v2` as the next SentenceTransformers model after MiniLM.
- Ollama embedding models such as `embeddinggemma:300m`.
- Larger local embedding models such as `qwen3-embedding:8b`.
- Custom fine-tuned scientific/patent embedding models remain a later option, not part of this PRD.

## User Stories

- As a researcher, I can choose `all-mpnet-base-v2` for higher-quality local semantic retrieval than the MiniLM baseline.
- As a researcher, I can choose local Ollama embedding models such as `embeddinggemma:300m`, so that embeddings can use the same local model runtime as chat.
- As a researcher with enough local resources, I can choose a larger model such as `qwen3-embedding:8b`, so that I can compare higher-capacity embeddings against smaller baselines.
- As a maintainer, I can validate model dimensions and provider compatibility before rebuilding an index.
- As a researcher, I can see which embedding provider/model produced each vector result.

## Scope

- Add `sentence-transformers/all-mpnet-base-v2` as a supported SentenceTransformers embedding model.
- Add an Ollama embedding provider path for models such as `embeddinggemma:300m` and `qwen3-embedding:8b`.
- Add a small model registry/settings layer that records provider, model name, expected vector dimension where known, distance metric compatibility, local resource notes, and whether the model must be present locally before rebuild.
- Validate vector dimension, distance metric, provider, and model compatibility before rebuild.
- Surface model/provider availability and setup errors clearly.
- Extend vector-search evaluation to compare supported embedding models on committed semantic/paraphrase fixtures.

## Out Of Scope

- Multiple immutable indexes per repository.
- Fine-tuned scientific or patent embedding model training.
- Hybrid retrieval and reranking, which remain covered by PRD6.
- Remote hosted embedding APIs. Embeddings remain local-first.

## Acceptance Criteria

- `sentence-transformers/all-mpnet-base-v2` can be selected, indexed, searched, and reported in result metadata.
- `embeddinggemma:300m` can be selected, indexed, searched, and reported in result metadata when available locally through Ollama.
- `qwen3-embedding:8b` or the current project-approved Qwen embedding model name can be selected, indexed, searched, and reported in result metadata when available locally through Ollama.
- Unsupported model/provider/distance combinations fail before index rebuild with actionable errors.
- Evaluation output records per-model semantic recall for MiniLM, mpnet, embeddinggemma, and Qwen where those models are available.
- Documentation explains model tradeoffs, expected vector dimensions, local resource expectations, setup steps, and how to pull/check Ollama embedding models.

## Test Plan

- Unit tests for model/provider compatibility and vector dimension validation.
- Deterministic provider tests for ordinary CI.
- Live/local tests for `sentence-transformers/all-mpnet-base-v2` when available.
- Live/local tests for `embeddinggemma:300m` and `qwen3-embedding:8b` when available through Ollama, gated behind the existing `live` marker.
- Evaluation comparison across MiniLM, mpnet, embeddinggemma, and Qwen when live models are enabled.

## Notes

PRD5 intentionally ships MiniLM first to keep the vector-search baseline small and reviewable. This PRD adds model breadth after the base vector lifecycle is stable, but it should not introduce immutable multi-index management; PRD16 owns retaining and comparing multiple embedding indexes over time.
