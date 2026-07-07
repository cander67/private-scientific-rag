# PRD 15: Additional Embedding Models

## Goal

Expand vector search beyond the initial MiniLM baseline so researchers can choose stronger or more specialized embedding models when local resources allow.

## User Stories

- As a researcher, I can choose `all-mpnet-base-v2` for higher-quality local semantic retrieval than the MiniLM baseline.
- As a researcher, I can choose local Ollama embedding models such as `embeddinggemma`, so that embeddings can use the same local model runtime as chat.
- As a maintainer, I can validate model dimensions and provider compatibility before rebuilding an index.
- As a researcher, I can see which embedding provider/model produced each vector result.

## Scope

- Add `all-mpnet-base-v2` as a supported SentenceTransformers embedding model.
- Add an Ollama embedding provider path for models such as `embeddinggemma`.
- Validate vector dimension, distance metric, provider, and model compatibility before rebuild.
- Surface model/provider availability and setup errors clearly.
- Extend vector-search evaluation to compare supported embedding models on committed semantic/paraphrase fixtures.

## Out Of Scope

- Multiple immutable indexes per repository.
- Fine-tuned scientific or patent embedding model training.
- Hybrid retrieval and reranking, which remain covered by PRD6.

## Acceptance Criteria

- `all-mpnet-base-v2` can be selected, indexed, searched, and reported in result metadata.
- Ollama embedding models can be selected, indexed, searched, and reported in result metadata when available locally.
- Unsupported model/provider/distance combinations fail before index rebuild with actionable errors.
- Evaluation output records per-model semantic recall for the committed fixture set.
- Documentation explains model tradeoffs, local resource expectations, and setup steps.

## Test Plan

- Unit tests for model/provider compatibility and vector dimension validation.
- Deterministic provider tests for ordinary CI.
- Live/local tests for one SentenceTransformers model and one Ollama embedding model when available.
- Evaluation comparison across MiniLM, mpnet, and at least one Ollama embedding model when live models are enabled.

## Notes

PRD5 intentionally ships MiniLM first to keep the vector-search baseline small and reviewable. This PRD adds model breadth after the base vector lifecycle is stable.
