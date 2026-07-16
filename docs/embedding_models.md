# Embedding Models

PRD15 expands vector search beyond the MiniLM baseline while keeping embeddings local-first. Repository settings choose one active embedding provider/model at a time, and vector rebuilds replace the repository's latest Qdrant collection with vectors from that active model.

## Provider Tradeoffs

SentenceTransformers models run inside the Python process. They are simple to use for CPU-first local search, integrate with the existing deterministic test boundary, and can support cosine, dot, or Euclidean distance when the model settings declare those metrics. The tradeoff is that model files must be available in the local SentenceTransformers cache before live rebuilds, and larger models increase local memory and indexing time.

Ollama embedding models run through the local Ollama service configured by `PRIVATE_RAG_OLLAMA_BASE_URL`. This keeps embedding downloads and runtime management aligned with the local chat model workflow. The tradeoff is an extra local service dependency: Ollama must be running, the model must be pulled, and the provider must return finite vectors with stable dimensions before rebuild continues. PRD15 supports known Ollama embedding models through one generic Ollama provider rather than one provider class per model.

Default CI does not download embedding models or require Ollama. Tests use deterministic fake embeddings and mocked Ollama responses unless a maintainer explicitly opts into live checks.

## Supported Models

| Provider | Model | Vector size | Distance metrics | Resource profile | Setup |
| --- | --- | ---: | --- | --- | --- |
| SentenceTransformers | `sentence-transformers/all-MiniLM-L6-v2` | 384 | `cosine`, `dot`, `euclid` | Small CPU-friendly baseline for fast indexing. | Cache with SentenceTransformers before live rebuilds. |
| SentenceTransformers | `sentence-transformers/all-mpnet-base-v2` | 768 | `cosine`, `dot`, `euclid` | Larger local model with stronger semantic retrieval quality than MiniLM in many general workloads. | Cache with SentenceTransformers before live rebuilds. |
| Ollama | `embeddinggemma:300m` | 768 | `cosine` | Lightweight Ollama embedding model with a smaller local footprint than the Qwen option. | Start Ollama, then run `ollama pull embeddinggemma:300m`. |
| Ollama | `qwen3-embedding:8b` | 4096 | `cosine` | Larger high-capacity local embedding model; expect materially higher memory, storage, and indexing cost. | Start Ollama, then run `ollama pull qwen3-embedding:8b`. |

The canonical source for this table is the embedding model registry in `src/private_rag/vector/model_registry.py`. Repository settings validation checks provider/model ownership, vector size, and distance compatibility before a vector rebuild replaces the latest index.

## Local Setup

To prepare SentenceTransformers models, load the model once in the project environment so it is cached locally:

```bash
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"
```

PowerShell:

```powershell
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-MiniLM-L6-v2')"
uv run python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('sentence-transformers/all-mpnet-base-v2')"
```

To prepare Ollama embedding models, start Ollama and pull the model:

```bash
ollama pull embeddinggemma:300m
ollama pull qwen3-embedding:8b
```

PowerShell:

```powershell
ollama pull embeddinggemma:300m
ollama pull qwen3-embedding:8b
```

Use `.env` to override local defaults when needed:

```dotenv
PRIVATE_RAG_OLLAMA_BASE_URL=http://localhost:11434
PRIVATE_RAG_DEFAULT_EMBEDDING_MODEL=sentence-transformers/all-MiniLM-L6-v2
```

The repository-scoped Settings / Models screen remains the source of truth for a repository's active embedding provider, embedding model, vector size, and distance metric. Changing those settings does not mutate existing vectors until the vector index is rebuilt.

## Custom Ollama Embedding Models

Known models should be added as `EmbeddingModelMetadata` entries in `src/private_rag/vector/model_registry.py`. Add the provider, model name, label, vector size, supported distances, resource notes, setup hint, and local-model requirement. No new provider class is needed for a normal Ollama embedding model because the generic Ollama provider sends the configured model name to `/api/embed`.

Unknown Ollama embedding model names are treated as advanced local entries. They can be used only when the runtime supports embeddings and a live dimension probe succeeds before rebuild. Unknown models are compatibility-checked, but they are not quality-vetted by PRD15.

## Evaluation

Vector evaluation can compare supported embedding models against committed semantic fixtures. Output records the provider, model, vector size, distance, fixture name, status, recall metrics, query count, and skip reason when a local dependency is unavailable.

Default evaluation tests stay deterministic. Live/local comparison is opt-in: run it only after the relevant SentenceTransformers cache entries, Ollama service, Ollama model pulls, and Qdrant service are ready.

## Latest Index Boundary

PRD15 keeps one latest vector index per repository. Rebuilding replaces that repository's latest Qdrant collection after validation passes, and search reports the embedding provider/model that produced the latest index.

PRD16 is the future immutable multi-index work. It will own retaining multiple embedding indexes, comparing them without replacing the active index, and managing index selection history over time.
