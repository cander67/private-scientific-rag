# Frontend

The frontend is a React/Vite app. PRD1 provides the shell, and the static mockups describe the planned repository, document manager, source viewer, search, chat, prompt sandbox, settings, and export workflows.

Current implementation status: PRD5 is implemented and ready for review. The production frontend includes distinct document manager, source viewer, and Search Lab views for upload, document selection, PDF page thumbnails, chunk provenance inspection, `needs_ocr`/zero-chunk inspection states, reprocess, delete, full-text retrieval inspection, and vector retrieval inspection.

Search Lab supports manual full-text and vector index rebuilds, query execution, top-k selection, document/section/source filters, table/figure/patent metadata filters, BM25 score display for full-text results, dense score and embedding metadata display for vector results, snippets or chunk previews, matched fields where available, and source navigation for matched chunks. Hybrid and reranking controls are intentionally disabled until PRD6.

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
