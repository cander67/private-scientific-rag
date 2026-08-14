# Frontend

The frontend is a React/Vite app. PRD1 provides the shell, and the static mockups describe the planned repository, document manager, source viewer, search, chat, prompt sandbox, settings, and export workflows.

Current implementation status: PRD1 through PRD9, PRD20 through PRD23, PRD25 through PRD28, and PRD30 are complete and closed. PRD28 Document Manager Preview and Batch Actions added row-click metadata preview, backend batch reprocess/OCR/delete contracts, checkbox multi-select, selected-action toolbar, reprocess-all confirmation, delete-selected confirmation, OCR eligibility copy, partial batch-result summaries, post-batch row/card/Source Viewer refresh, and stale retrieval guidance. PRD13 Parser Selection, OCR, and Page-Image Text Recovery is ready for final review pending user acceptance and the PRD29 manual acceptance pass. PRD32 Workflow Friction Remediation is ready for final review pending user acceptance after bottom Settings / Models save controls, chat rename/default-title remediation, stale parser/chunk repair actions in Search Lab and Chat Workspace, and expandable full-context Chat Workspace inspection. The production frontend includes Repository Dashboard, document manager, source viewer, Search Lab, Chat Workspace, Prompt Sandbox, Settings / Models, Export Center, and Recreate Repository views for home/status navigation, upload, document selection, row-click metadata preview, checkbox multi-select, selected/full-repository document batch actions, post-batch row/card/Source Viewer refresh, PDF page thumbnails, chunk provenance inspection, token count/window/tokenizer inspection, `needs_ocr`/zero-chunk inspection states, reprocess, readable parser route/version details, OCR recovery actions, recovered OCR page text, OCR-derived chunk labels, row-level delete, delete-all, repository default settings, full-text/vector/hybrid/reranked retrieval inspection, local RAG chat with citations and context inspection, prompt/retrieval/model comparison, portable ZIP export, and bundle validation/recreate.

Repository Dashboard is the default home route for empty hash, `#home`, and `#repository-dashboard`. It shows active repository identity, repository switching, document/chunk/chat/retrieval/sandbox/export/recreate counts, full-text/vector missing/partial/stale/ready status, Qdrant/chat/embedding/reranker readiness, active configuration, warnings, navigation-only quick actions, and recent activity. The no-repository state offers using the default repository or opening Recreate Repository; it does not expose destructive reset/delete controls.

Search Lab supports manual full-text and vector index rebuilds, query execution through the unified retrieval API, full-text/vector/hybrid mode selection, reranking strategy selection, candidate-pool and RRF controls, metadata boost level selection including `off`, top-k selection, document/section/source filters, table/figure/patent metadata filters, BM25/dense/RRF/rerank/boost/final score display, per-dimension metadata boost breakdowns, snippets or chunk previews, matched fields where available, source navigation for matched chunks, stale parser/chunk repository reprocess actions that reuse the PRD28 batch contract, and explicit actions to copy the current retrieval configuration into Chat Workspace or promote it to repository defaults.

Chat Workspace uses chat retrieval settings snapshotted from repository defaults when a new session starts, rather than inheriting Search Lab controls implicitly. The retrieval panel lets users choose chat mode, reranker, top-k, candidate pool, RRF constant, metadata boost dimensions including `off`, and a document-kind filter; check full-text/vector/local-model readiness; see the configured retrieval embedding model and latest vector-index model; explicitly rebuild full-text or vector indexes; repair stale parser/chunk state through repository reprocess before rebuilding; and send questions to the local Ollama model. Chat does not rebuild indexes automatically. Chat sessions can be renamed, deleted individually, or cleared for the repository, and untitled new sessions use distinct deterministic default titles. Citation cards include source metadata and preview text, and their source action opens the cited document/chunk in Source Viewer. Draft questions expose `Inspect context` before send, and assistant answers with persisted snapshots expose the same action after completion. The inspector modal shows model, active prompt, retrieval settings, chat history, compact retrieved-context previews with expand/collapse full chunk text, assembled LLM messages containing the full context sent to the model, retrieval-run details, status, warnings, empty states, and source links for retrieved chunks. It is read-only normal-chat transparency, while Prompt Sandbox remains the owner of side-by-side prompt/retrieval/model experiments. The composer follows the end of the chat thread until the available page height is reached, then the message list scrolls while the query field remains visible.

Prompt Sandbox lets users save isolated sandbox prompt versions, copy prompts to/from the repository chat prompt library, delete sandbox versions, run four-mode full-text/vector/hybrid/reranked comparisons, see each retrieval mode complete progressively, and inspect answers, prompt snapshots, effective retrieval settings, citations, latency, context counts, and source links without changing Chat Workspace defaults.

Export Center lets users review repository counts, model/settings requirements, source-file inclusion, and opt-in sandbox export before creating a PRD9 ZIP bundle. Successful exports show a download action and manifest-style summary; failures are surfaced in the panel without blocking the rest of the app.

Recreate Repository lets users select an export ZIP, validate it before restore, review blocking errors/warnings/informational checks, provide external source mappings, restore into a new or existing empty repository, and inspect the final source/index report.

Settings / Models includes PRD13 parser/chunking/OCR controls, PRD23 model catalog guardrails, PRD27 repository retrieval defaults, and PRD30 token chunking vocabulary. The page loads the repository model catalog, renders known parser and OCR provider choices, lets chunking defaults choose recursive segment-aware token coalescing or fixed-size token windows, identifies the 512-token/64-token-overlap default, shows the resolved chunk tokenizer ID/library/precision, exposes advanced manual tokenizer selection from the catalog, lets OCR defaults control provider, fallback provider, fallback enablement, language, confidence threshold, minimum text length, max pages, and overwrite behavior, renders known embedding providers/models as selectors, derives dimensions for known embeddings, disables incompatible distances, offers catalog-backed chat and reranker choices, lets repository retrieval defaults control mode/top-k/candidate pool/RRF/reranker strategy/metadata boosts/filters, explains Qdrant collection state/rebuild impact with links to Search Lab and Repository Administration, and keeps custom local model entry available with explicit probe/compatibility guidance. Source Viewer shows parser names/routes before dependency version numbers and exposes per-chunk token counts, token windows, tokenizer ID, implementation library, source, selection mode, offset support, and fallback precision. Explicit readiness checks remain user-triggered and use the backend readiness vocabulary for unavailable runtime, missing model, failed/load-in-progress, skipped, and ready states.

PRD17 is in the backlog to clarify Search Lab result labels by separating chunk-level facts, document-level hints, parser hints, and active filters.

The candidate pool defaults to `top_k * 5`, RRF defaults to `60`, and metadata boosts use user-selectable Off/Low/Medium/High levels. Cross-encoder reranking requires its configured model in the backend's local model cache. Diversity/MMR is intentionally displayed as a future option.

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
