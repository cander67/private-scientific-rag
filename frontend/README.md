# Frontend

The frontend is a React/Vite app. PRD1 provides the shell, and the static mockups describe the planned repository, document manager, source viewer, search, chat, prompt sandbox, settings, and export workflows.

Current implementation status: PRD3 is complete. The production frontend includes the document manager/source inspector for upload, document selection, PDF page thumbnails, chunk provenance inspection, `needs_ocr`/zero-chunk inspection states, reprocess, and delete.

PRD4 full-text search is next. Bulk patent-data workflows are planned separately in PRD12.

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
