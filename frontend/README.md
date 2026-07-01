# Frontend

The frontend is a React/Vite app. PRD1 provides the shell, and the static mockups describe the planned repository, document manager, source viewer, search, chat, prompt sandbox, settings, and export workflows.

Current implementation status: the production frontend shell is still minimal. PRD3 will introduce source inspection UI for uploaded documents, including user-uploaded patent PDFs. Bulk patent-data workflows are planned separately in PRD12.

Run locally:

```bash
npm install
npm run dev
```

Build:

```bash
npm run build
```

The backend API defaults to `http://127.0.0.1:8000`.
