# Frontend

The frontend is a React/Vite app. PRD1 provides the shell, and the static mockups describe the planned repository, document manager, source viewer, search, chat, prompt sandbox, settings, and export workflows.

Current implementation status: PRD6 is complete and closed. PRD7 is in progress. The production frontend includes distinct document manager, source viewer, and Search Lab views for upload, document selection, PDF page thumbnails, chunk provenance inspection, `needs_ocr`/zero-chunk inspection states, reprocess, delete, and full-text, vector, hybrid, and reranked retrieval inspection.

Search Lab supports manual full-text and vector index rebuilds, query execution through the unified retrieval API, full-text/vector/hybrid mode selection, reranking strategy selection, candidate-pool and RRF controls, metadata boost level selection, top-k selection, document/section/source filters, table/figure/patent metadata filters, BM25/dense/RRF/rerank/boost/final score display, snippets or chunk previews, matched fields where available, and source navigation for matched chunks.

PRD17 is in the backlog to clarify Search Lab result labels by separating chunk-level facts, document-level hints, parser hints, and active filters.

The candidate pool defaults to `top_k * 5`, RRF defaults to `60`, and metadata boosts use user-selectable High/Medium/Low levels. Cross-encoder reranking requires its configured model in the backend's local model cache. Diversity/MMR is intentionally displayed as a future option.

Bulk patent-data workflows are planned separately in PRD12.

Run locally:

```bash
npm install
npm run dev
```

Build:

```bash
npm run build
```

Run frontend contract tests:

```bash
npm test
```

The backend API defaults to `http://127.0.0.1:8000`.
