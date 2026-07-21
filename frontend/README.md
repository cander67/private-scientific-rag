# Frontend

The frontend is a React/Vite app. PRD1 provides the shell, and the static mockups describe the planned repository, document manager, source viewer, search, chat, prompt sandbox, settings, and export workflows.

Current implementation status: PRD1 through PRD9, PRD20, PRD21, and PRD22 are complete and closed. PRD13 Parser Selection, OCR, and Page-Image Text Recovery and PRD23 Settings Model Catalog and Collection Guardrails are ready for final review. The production frontend includes Repository Dashboard, document manager, source viewer, Search Lab, Chat Workspace, Prompt Sandbox, Settings / Models, Export Center, and Recreate Repository views for home/status navigation, upload, document selection, PDF page thumbnails, chunk provenance inspection, `needs_ocr`/zero-chunk inspection states, reprocess, OCR recovery actions, recovered OCR page text, OCR-derived chunk labels, row-level delete, delete-all, repository default settings, full-text/vector/hybrid/reranked retrieval inspection, local RAG chat with citations, prompt/retrieval/model comparison, portable ZIP export, and bundle validation/recreate.

Repository Dashboard is the default home route for empty hash, `#home`, and `#repository-dashboard`. It shows active repository identity, repository switching, document/chunk/chat/retrieval/sandbox/export/recreate counts, full-text/vector missing/partial/stale/ready status, Qdrant/chat/embedding/reranker readiness, active configuration, warnings, navigation-only quick actions, and recent activity. The no-repository state offers using the default repository or opening Recreate Repository; it does not expose destructive reset/delete controls.

Search Lab supports manual full-text and vector index rebuilds, query execution through the unified retrieval API, full-text/vector/hybrid mode selection, reranking strategy selection, candidate-pool and RRF controls, metadata boost level selection, top-k selection, document/section/source filters, table/figure/patent metadata filters, BM25/dense/RRF/rerank/boost/final score display, snippets or chunk previews, matched fields where available, and source navigation for matched chunks.

Chat Workspace uses separate chat retrieval settings rather than inheriting Search Lab controls. The retrieval panel lets users choose chat mode, reranker, and top-k; check full-text/vector/local-model readiness; see the configured retrieval embedding model and latest vector-index model; explicitly rebuild full-text or vector indexes; and send questions to the local Ollama model. Chat does not rebuild indexes automatically. Chat sessions can be deleted individually or cleared for the repository. Citation cards include source metadata and preview text, and their source action opens the cited document/chunk in Source Viewer. The composer follows the end of the chat thread until the available page height is reached, then the message list scrolls while the query field remains visible.

Prompt Sandbox lets users save isolated sandbox prompt versions, copy prompts to/from the repository chat prompt library, delete sandbox versions, run four-mode full-text/vector/hybrid/reranked comparisons, see each retrieval mode complete progressively, and inspect answers, prompt snapshots, settings, citations, latency, context counts, and source links without changing Chat Workspace defaults.

Export Center lets users review repository counts, model/settings requirements, source-file inclusion, and opt-in sandbox export before creating a PRD9 ZIP bundle. Successful exports show a download action and manifest-style summary; failures are surfaced in the panel without blocking the rest of the app.

Recreate Repository lets users select an export ZIP, validate it before restore, review blocking errors/warnings/informational checks, provide external source mappings, restore into a new or existing empty repository, and inspect the final source/index report.

Settings / Models includes PRD13 parser/chunking/OCR controls and PRD23 model catalog guardrails. The page loads the repository model catalog, renders known parser and OCR provider choices, lets chunking defaults choose recursive segment-aware coalescing or fixed-size windows, lets OCR defaults control provider, fallback provider, fallback enablement, language, confidence threshold, minimum text length, max pages, and overwrite behavior, renders known embedding providers/models as selectors, derives dimensions for known embeddings, disables incompatible distances, offers catalog-backed chat and reranker choices, explains Qdrant collection state/rebuild impact with links to Search Lab and Repository Administration, and keeps custom local model entry available with explicit probe/compatibility guidance. Source Viewer shows parser names/routes before dependency version numbers. Explicit readiness checks remain user-triggered and use the backend readiness vocabulary for unavailable runtime, missing model, failed/load-in-progress, skipped, and ready states.

PRD17 is in the backlog to clarify Search Lab result labels by separating chunk-level facts, document-level hints, parser hints, and active filters.

The candidate pool defaults to `top_k * 5`, RRF defaults to `60`, and metadata boosts use user-selectable High/Medium/Low levels. Cross-encoder reranking requires its configured model in the backend's local model cache. Diversity/MMR is intentionally displayed as a future option.

Repository chat prompts are stored in backend repository settings as a prompt library with an active chat prompt ID. The default prompt instructs the local model to answer only from repository context, use inline citations, and say when the retrieved context does not contain enough evidence.

Bulk patent-data workflows are planned separately in PRD12.

Run locally:

```bash
npm install
npm run dev
```

PowerShell:

```powershell
npm install
npm run dev
```

Build:

```bash
npm run build
```

PowerShell:

```powershell
npm run build
```

Run frontend contract tests:

```bash
npm test
```

PowerShell:

```powershell
npm test
```

The backend API defaults to `http://127.0.0.1:8000`.
