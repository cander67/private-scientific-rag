# Frontend

The frontend is a React/Vite app. PRD1 provides the shell, and the static mockups describe the planned repository, document manager, source viewer, search, chat, prompt sandbox, settings, and export workflows.

Current implementation status: PRD1 through PRD9 are complete and closed. The production frontend includes distinct document manager, source viewer, Search Lab, Chat Workspace, Prompt Sandbox, Export Center, and Recreate Repository views for upload, document selection, PDF page thumbnails, chunk provenance inspection, `needs_ocr`/zero-chunk inspection states, reprocess, row-level delete, delete-all, full-text/vector/hybrid/reranked retrieval inspection, local RAG chat with citations, prompt/retrieval/model comparison, portable ZIP export, and bundle validation/recreate.

Search Lab supports manual full-text and vector index rebuilds, query execution through the unified retrieval API, full-text/vector/hybrid mode selection, reranking strategy selection, candidate-pool and RRF controls, metadata boost level selection, top-k selection, document/section/source filters, table/figure/patent metadata filters, BM25/dense/RRF/rerank/boost/final score display, snippets or chunk previews, matched fields where available, and source navigation for matched chunks.

Chat Workspace uses separate chat retrieval settings rather than inheriting Search Lab controls. The retrieval panel lets users choose chat mode, reranker, and top-k; check full-text/vector/local-model readiness; explicitly rebuild full-text or vector indexes; and send questions to the local Ollama model. Chat does not rebuild indexes automatically. Chat sessions can be deleted individually or cleared for the repository. Citation cards include source metadata and preview text, and their source action opens the cited document/chunk in Source Viewer. The composer follows the end of the chat thread until the available page height is reached, then the message list scrolls while the query field remains visible.

Prompt Sandbox lets users save isolated sandbox prompt versions, copy prompts to/from the repository chat prompt library, delete sandbox versions, run four-mode full-text/vector/hybrid/reranked comparisons, see each retrieval mode complete progressively, and inspect answers, prompt snapshots, settings, citations, latency, context counts, and source links without changing Chat Workspace defaults.

Export Center lets users review repository counts, model/settings requirements, source-file inclusion, and opt-in sandbox export before creating a PRD9 ZIP bundle. Successful exports show a download action and manifest-style summary; failures are surfaced in the panel without blocking the rest of the app.

Recreate Repository lets users select an export ZIP, validate it before restore, review blocking errors/warnings/informational checks, provide external source mappings, restore into a new or existing empty repository, and inspect the final source/index report.

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
