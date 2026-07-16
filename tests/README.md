# Tests

Tests are split by speed and dependency profile:

- `tests/unit/`: fast tests for pure functions, settings, models, and validation.
- `tests/integration/`: local app integration tests that avoid real LLM/model calls by default.

Live tests that require local services or models use the `live` marker and do not run by default.

PRD3 ingestion/source-inspection coverage is complete. Default CI does not read from `documents/golden_corpus/`; that directory is local/manual evaluation material. Tests use committed fixtures in `tests/fixtures/ingestion/` plus generated miniature PDFs for text-layer and image-only OCR-gate behavior. Larger files in `documents/golden_corpus/pdf/` and `documents/golden_corpus/ocr/` are useful for local/manual parser checks and future OCR work, but should not be default CI prerequisites unless they are intentionally copied into `tests/fixtures/` with redistribution approval.

PRD4 full-text search coverage includes unit tests for FTS query normalization and field weights, API integration coverage for rebuilding a repository index and searching citation-ready chunk results, metadata filter coverage, repository settings snapshot coverage, and CI exact-match recall evaluation.

Exact-match search fixtures live in `tests/fixtures/search/`. They cover formulas, abbreviations, identifiers, patent terms, and section headings, and require `recall@5` and `recall@10` to remain at `1.0` for the committed fixture set.

PRD5 vector search coverage uses deterministic fake embeddings and an in-memory vector store for ordinary CI. It covers vector rebuild/search API behavior, latest-index replacement metadata, full-text-equivalent filters, missing-index errors, and semantic recall evaluation. The committed semantic fixture is `tests/fixtures/search/prd5_semantic_fixture.json`.

PRD6 retrieval coverage includes deterministic integration tests for the unified retrieval API and evaluation comparison. The tests exercise full-text mode, vector mode with fake embeddings and an in-memory vector store, hybrid RRF mode, normalized score breakdowns, retrieval run/result persistence, max-five recent history retention, strategy validation, cross-encoder reranking through a fake provider, metadata boost scoring, and comparison metrics for full-text, vector, hybrid, and reranked hybrid. Unit tests cover RRF merging for sparse-only, dense-only, overlapping, adjusted-constant cases, reranker score composition, and missing cross-encoder setup guidance.

PRD7 chat coverage keeps CI deterministic by mocking the LLM at the chat boundary. Default tests cover repository prompt-library settings, prompt/context assembly, citation-token mapping, model registry responses, chat session/message persistence, hybrid retrieval wiring with a fake reranker, and assistant citation metadata persisted from a mocked LLM response. Live local LLM tests are separate opt-in commands.

PRD8 Prompt Sandbox coverage keeps CI deterministic by mocking the LLM at the sandbox boundary. Default tests cover sandbox prompt version validation, repository-scoped create/list/read/copy/delete behavior, side-by-side comparison persistence, progressive per-run comparison execution, prompt snapshot preservation, retrieved context snapshots, generated answers, citations, latency, and frontend contract coverage for the Prompt Sandbox view. Golden query datasets, aggregate retrieval metrics, and evidence-backed promotion to chat defaults are deferred to PRD18.

PRD9 export/import/recreate coverage includes the portable bundle contract, bundle validation, backend recreate execution, Export Center, and Recreate Repository UI contracts. Default tests cover deterministic source bundle paths and SHA-256 hashing, manifest schema validation, ZIP structure, default source inclusion, chat/retrieval/chunk/citation payload export, opt-in sandbox payload export, malformed/unsupported bundle rejection, missing payload detection, source hash mismatches, external source mapping failures, renamed-file warnings, missing model reports, parser fingerprints, exported count summaries, recreate into a new repository, recreate into an explicit empty repository, source-excluded recreate through external mappings, active chat/retrieval history remapping, deterministic full-text/vector rebuild reporting, validation display, blocked recreate, successful recreate progress, and final report display.

PRD20 Repository Dashboard coverage keeps dashboard summary checks deterministic by mocking service/model readiness boundaries. Backend integration tests cover empty and populated repository summaries, repository-scoped counts, full-text/vector missing/partial/stale/ready index states, unavailable readiness warnings, recreated repository summary after restore, and recent activity ordering/scoping. Frontend contract tests cover empty hash/`#home`/`#repository-dashboard` aliases, sidebar navigation, dashboard summary rendering, readiness labels, warning links, repository switching, no-repository recovery, quick-action links, and recent activity routing. Live Qdrant/local-model checks remain opt-in through the existing live test commands.

PRD21 Settings / Models coverage keeps default CI deterministic by mocking service and model boundaries. Unit and integration tests cover repository settings validation, prompt-library invariants, impact categories, settings round-trip/repository scoping, manifest/export reflection, explicit readiness responses for Qdrant/chat/embedding/reranker, chat readiness using the saved repository chat model, and non-finite embedding guards. Frontend contract tests cover the Settings / Models route, grouped editable defaults, save/cancel validation, impact warnings, readiness labels, workflow follow-up links, chat/export default propagation, and preservation of Search Lab, Chat Workspace, and Prompt Sandbox per-run overrides. Live Qdrant, Ollama, SentenceTransformers, and cross-encoder checks remain opt-in below.

PRD22 Ollama chat model expansion keeps default CI deterministic by mocking the chat LLM boundary. Unit and integration tests cover chat registry metadata, repository default and custom model propagation, missing-model readiness guidance, Settings / Models backend-fed registry controls, Prompt Sandbox per-run model suggestions, and persisted model metadata on chat/sandbox outputs. Live Ollama checks remain opt-in because they require a running local runtime and pulled model tags.

PRD23 Settings model catalog coverage keeps catalog loading deterministic and separate from runtime probes. Unit and integration tests cover the repository-scoped model catalog response, known embedding dimensions and supported distances, known chat and reranker choices, and the not-checked runtime detection section that avoids Ollama calls or local model loading by default. Frontend contract tests cover Settings / Models catalog loading, known embedding dropdowns, derived read-only dimensions, disabled incompatible distances, catalog-backed chat/reranker choices, disabled reranking, detected-versus-known labels, Qdrant collection explanation/state/workflow links, and advanced custom model paths.

PRD19 Repository Administration coverage keeps destructive cleanup deterministic and isolated. Default tests use temporary data directories, test databases, app-managed sample files, external sample files, and fake vector stores to verify preview, guarded one-repository deletion, clear-all recovery, preserved external files/model caches, full-text cleanup, Qdrant-unavailable warnings, and retrying leftover vector collections without deleting a repository twice. Live Qdrant cleanup checks are not part of default CI; run them only against disposable local collections during an explicit manual review window.

PRD15 embedding model coverage keeps default CI deterministic by using fake embeddings, mocked Ollama responses, and the in-memory vector store. Unit and integration tests cover the model registry, provider/model/distance validation, repository-scoped provider selection, mocked Ollama embedding responses, rebuild/search metadata, model-comparison evaluation output, and skipped unavailable models. Live model comparison remains opt-in because it requires local SentenceTransformers cache entries, Qdrant, Ollama, and pulled Ollama embedding models.

PRD9-focused deterministic commands:

```bash
uv run pytest tests/unit/test_export_bundle.py tests/integration/test_export_bundle_api.py
cd frontend
npm test
```

PowerShell:

```powershell
uv run pytest tests/unit/test_export_bundle.py tests/integration/test_export_bundle_api.py
Set-Location frontend
npm test
Set-Location ..
```

The cross-platform manual transfer checklist and warning glossary live in `docs/export_recreate.md`. Optional live checks for Qdrant, cross-encoder reranking, Ollama, and local RAG chat are listed below.

## Live tests

Default CI and `uv run pytest` exclude live tests. Run live checks only when the required local service or model is already available.

### Vector/Qdrant live smoke

Prerequisites:

- Qdrant is running at the configured `qdrant_url` (`http://127.0.0.1:6333` by default).
- The default SentenceTransformers embedding model can be loaded locally. If it is not cached, SentenceTransformers may download it during this explicit live run.

Run:

```bash
docker compose up -d qdrant
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_vector_live.py
```

PowerShell:

```powershell
docker compose up -d qdrant
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live tests/integration/test_vector_live.py
Remove-Item Env:\RUN_LIVE_TESTS
```

### Additional embedding model setup

PRD15 model-comparison evaluation can exercise MiniLM, mpnet, `embeddinggemma:300m`, and `qwen3-embedding:8b` when each is available locally. See `docs/embedding_models.md` for provider tradeoffs, dimensions, and setup commands. Default CI does not download these models or require Ollama; unavailable live models should be reported as skipped with setup guidance.

### Cross-encoder live smoke

Prerequisites:

- The configured cross-encoder model is downloaded/cached locally. The default is `cross-encoder/ms-marco-MiniLM-L6-v2`.
- Retrieval API calls use `local_files_only=True` for cross-encoder reranking, so a missing model returns setup guidance instead of silently downloading during search.

Download/cache the default model:

```bash
uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"
```

PowerShell:

```powershell
uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"
```

Run:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_cross_encoder_live.py
```

PowerShell:

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live tests/integration/test_cross_encoder_live.py
Remove-Item Env:\RUN_LIVE_TESTS
```

### Ollama chat live smoke

Prerequisites:

- Ollama is running at the configured `ollama_base_url` (`http://localhost:11434` by default).
- The default or custom chat model is installed. The default is `gemma3:4b`; registry and custom tags use the same generic `/api/chat` provider.

Download/cache the default chat model, or substitute another configured model:

```bash
ollama pull gemma3:4b
```

PowerShell:

```powershell
ollama pull gemma3:4b
```

Run the lightweight Ollama boundary check:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_ollama_live.py
```

PowerShell:

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live tests/integration/test_ollama_live.py
Remove-Item Env:\RUN_LIVE_TESTS
```

### Local RAG chat live smoke

This slower check creates a tiny fixture repository, rebuilds deterministic in-memory full-text/vector test indexes, calls the real local Ollama chat model, and verifies that the assistant response stores mapped citations. It keeps embedding and reranking deterministic so failures point mostly at the local LLM setup and chat path.

Prerequisites are the same as the Ollama chat live smoke.

Run:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_chat_rag_live.py
```

PowerShell:

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live tests/integration/test_chat_rag_live.py
Remove-Item Env:\RUN_LIVE_TESTS
```

### Prompt Sandbox live note

Prompt Sandbox product runs use the selected local chat model through the same local LLM boundary as Chat Workspace. PRD8 default CI uses mocked generation for determinism. A separate opt-in sandbox live smoke is deferred until PRD18 adds maintainer evaluation and promotion workflows.

Golden corpus planning currently lives in `documents/golden_corpus/golden_corpus_manifest.md`; `golden_corpus_manifest_v1.md` is a frozen historical copy.

Run all default tests:

```bash
uv run pytest
```

PowerShell:

```powershell
uv run pytest
```

Run all default tests plus all opted-in live tests in one coverage pass:

```bash
RUN_LIVE_TESTS=1 uv run pytest -m "not live or live"
```

PowerShell:

```powershell
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m "not live or live"
Remove-Item Env:\RUN_LIVE_TESTS
```

Run backend tests by tier, including live tests when ready:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration
```

PowerShell:

```powershell
uv run pytest tests/unit
uv run pytest tests/integration
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live tests/integration
Remove-Item Env:\RUN_LIVE_TESTS
```

Run the full backend quality gate:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

PowerShell:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
```

Run the full backend quality gate with live tests included in the same coverage report:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
RUN_LIVE_TESTS=1 uv run pytest -m "not live or live"
```

PowerShell:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m "not live or live"
Remove-Item Env:\RUN_LIVE_TESTS
```

Run a specific group:

```bash
uv run pytest tests/unit
uv run pytest tests/integration
```

PowerShell:

```powershell
uv run pytest tests/unit
uv run pytest tests/integration
```

Coverage is configured in `pyproject.toml`, results are output to the terminal and can also be found in `htmlcov/index.html`.
