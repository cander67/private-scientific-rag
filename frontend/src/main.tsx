import React, { useEffect, useMemo, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

const API_BASE = "http://127.0.0.1:8000";

type RepositoryResponse = {
  repository: {
    id: string;
    name: string;
  };
};

type DocumentVersion = {
  id: string;
  source_type: "pdf" | "text" | "markdown" | "annotation";
  status: "parsed" | "needs_ocr" | "failed" | "skipped";
  parser_name: string;
  parser_version: string;
  original_filename: string;
  sha256: string;
  byte_size: number;
  chunk_count: number;
  page_count: number | null;
  line_count: number | null;
  section_count: number;
  ocr_required: boolean;
  warnings: string[];
  metadata: Record<string, unknown>;
  created_at: string;
};

type DocumentSummary = {
  id: string;
  display_name: string;
  current_version: DocumentVersion | null;
};

type Chunk = {
  id: string;
  chunk_index: number;
  text: string;
  section: string | null;
  page_start: number | null;
  page_end: number | null;
  line_start: number | null;
  line_end: number | null;
  char_start: number | null;
  char_end: number | null;
  parser_version: string;
  metadata: Record<string, unknown>;
};

type Inspection = {
  document: DocumentSummary;
  version: DocumentVersion;
  chunks: Chunk[];
};

function App() {
  const [repository, setRepository] = useState<RepositoryResponse["repository"] | null>(null);
  const [documents, setDocuments] = useState<DocumentSummary[]>([]);
  const [selectedDocumentId, setSelectedDocumentId] = useState<string | null>(null);
  const [inspection, setInspection] = useState<Inspection | null>(null);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("Loading repository");
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [selectedChunkId, setSelectedChunkId] = useState<string | null>(null);
  const [theme, setTheme] = useState<"light" | "dark">("light");
  const [navOpen, setNavOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    void loadRepository();
  }, []);

  useEffect(() => {
    if (repository) {
      void loadDocuments(repository.id);
    }
  }, [repository]);

  useEffect(() => {
    if (repository && selectedDocumentId) {
      void inspectDocument(repository.id, selectedDocumentId);
    }
  }, [repository, selectedDocumentId]);

  useEffect(() => {
    setSelectedChunkId(inspection?.chunks[0]?.id ?? null);
  }, [inspection]);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );

  const selectedChunk = useMemo(
    () => inspection?.chunks.find((chunk) => chunk.id === selectedChunkId) ?? inspection?.chunks[0] ?? null,
    [inspection, selectedChunkId],
  );

  const filteredDocuments = useMemo(
    () =>
      documents.filter((document) => {
        const version = document.current_version;
        const matchesQuery = document.display_name.toLowerCase().includes(query.toLowerCase());
        const matchesStatus = statusFilter === "all" || version?.status === statusFilter;
        return matchesQuery && matchesStatus;
      }),
    [documents, query, statusFilter],
  );

  const totalChunks = documents.reduce(
    (sum, document) => sum + (document.current_version?.chunk_count ?? 0),
    0,
  );

  async function loadRepository() {
    try {
      const response = await fetch(`${API_BASE}/repositories/default`);
      const payload = (await response.json()) as RepositoryResponse;
      setRepository(payload.repository);
      setMessage("Ready");
    } catch {
      setMessage("Backend unavailable");
    }
  }

  async function loadDocuments(repositoryId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/documents`);
      const payload = (await response.json()) as DocumentSummary[];
      setDocuments(payload);
      if (!selectedDocumentId && payload.length > 0) {
        setSelectedDocumentId(payload[0].id);
      }
    } catch {
      setMessage("Could not load documents");
    }
  }

  async function inspectDocument(repositoryId: string, documentId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/documents/${documentId}`);
      const payload = (await response.json()) as Inspection;
      setInspection(payload);
    } catch {
      setMessage("Could not inspect document");
    }
  }

  async function uploadFiles(files: FileList | null) {
    if (!repository || !files || files.length === 0) {
      return;
    }
    setBusy(true);
    setMessage(`Uploading ${files.length} file${files.length === 1 ? "" : "s"}`);
    try {
      for (const file of Array.from(files)) {
        const body = new FormData();
        body.append("file", file);
        const response = await fetch(`${API_BASE}/repositories/${repository.id}/documents`, {
          method: "POST",
          body,
        });
        if (!response.ok) {
          throw new Error(file.name);
        }
        const payload = (await response.json()) as { document: DocumentSummary };
        setSelectedDocumentId(payload.document.id);
      }
      await loadDocuments(repository.id);
      setMessage("Upload complete");
    } catch {
      setMessage("Upload failed");
    } finally {
      setBusy(false);
    }
  }

  async function reprocessSelected() {
    if (!repository || !selectedDocumentId) {
      return;
    }
    setBusy(true);
    setMessage("Reprocessing document");
    try {
      const response = await fetch(
        `${API_BASE}/repositories/${repository.id}/documents/${selectedDocumentId}/reprocess`,
        { method: "POST" },
      );
      setInspection((await response.json()) as Inspection);
      await loadDocuments(repository.id);
      setMessage("Reprocess complete");
    } catch {
      setMessage("Reprocess failed");
    } finally {
      setBusy(false);
    }
  }

  async function deleteSelected() {
    if (!repository || !selectedDocumentId) {
      return;
    }
    setBusy(true);
    setMessage("Deleting document");
    try {
      await fetch(`${API_BASE}/repositories/${repository.id}/documents/${selectedDocumentId}`, {
        method: "DELETE",
      });
      setSelectedDocumentId(null);
      setInspection(null);
      await loadDocuments(repository.id);
      setMessage("Deleted");
    } catch {
      setMessage("Delete failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <>
      <div
        className={navOpen ? "nav-scrim open" : "nav-scrim"}
        onClick={() => setNavOpen(false)}
      />
      <div className="app">
        <aside className={navOpen ? "sidebar open" : "sidebar"}>
          <div className="brand">
            <span className="mark" />
            <div>
              mml-rag<small>local scientific RAG</small>
            </div>
          </div>
          <nav className="nav">
            <a>Home</a>
            <span className="nav-label">Workspace</span>
            <a>Repository Dashboard</a>
            <a className="active">Document Manager</a>
            <a className={inspection ? "active-secondary" : ""}>Source Viewer</a>
            <a>Search Lab</a>
            <a>Prompt Sandbox</a>
            <a>Chat Workspace</a>
            <span className="nav-label">Manage</span>
            <a>Settings / Models</a>
            <a>Recreate Repository</a>
            <a>Export Center</a>
          </nav>
          <div className="sidebar-foot">
            <span className="status ok">Local-only mode</span>
          </div>
        </aside>

        <main className="content">
          <header className="topbar">
            <div className="row">
              <button
                className="hamburger"
                type="button"
                aria-label="Open navigation"
                onClick={() => setNavOpen(true)}
              >
                <span />
              </button>
              <div className="titles">
                <h1>Document Manager</h1>
                <p>{repository?.name ?? "Default Repository"} · {message}</p>
              </div>
            </div>
            <div className="topbar-actions">
              <label className="btn btn-primary upload-button">
                Upload documents
                <input
                  type="file"
                  multiple
                  accept=".pdf,.txt,.md,.markdown,.ann,application/pdf,text/plain,text/markdown"
                  onChange={(event) => void uploadFiles(event.target.files)}
                  disabled={busy || !repository}
                />
              </label>
              <button
                className="theme-toggle"
                type="button"
                onClick={() => setTheme(theme === "light" ? "dark" : "light")}
              >
                {theme === "light" ? "Dark" : "Light"}
              </button>
            </div>
          </header>

          <div className="page">
            <label className="dropzone">
              <input
                type="file"
                multiple
                accept=".pdf,.txt,.md,.markdown,.ann,application/pdf,text/plain,text/markdown"
                onChange={(event) => void uploadFiles(event.target.files)}
                disabled={busy || !repository}
              />
              <p>
                <strong>Drop PDF, TXT, Markdown, or ANN files here</strong>
              </p>
              <p className="muted">or use the Upload button. Duplicate files are skipped by hash.</p>
            </label>

            <div className="row row-between">
              <div className="row">
                <input
                  type="search"
                  placeholder="Filter by name..."
                  value={query}
                  onChange={(event) => setQuery(event.target.value)}
                  style={{ width: 220 }}
                />
                <select
                  value={statusFilter}
                  onChange={(event) => setStatusFilter(event.target.value)}
                  style={{ width: "auto" }}
                >
                  <option value="all">All statuses</option>
                  <option value="parsed">Parsed</option>
                  <option value="needs_ocr">Needs OCR</option>
                  <option value="failed">Failed</option>
                  <option value="skipped">Skipped</option>
                </select>
              </div>
              <span className="muted">
                {documents.length} documents · {totalChunks} chunks
              </span>
            </div>

            <div className="grid grid-side">
              <div className="table-wrap">
                <table>
                  <thead>
                    <tr>
                      <th>Document</th>
                      <th>Status</th>
                      <th>Pages</th>
                      <th>Chunks</th>
                      <th>Uploaded</th>
                      <th />
                    </tr>
                  </thead>
                  <tbody>
                    {filteredDocuments.length === 0 ? (
                      <tr>
                        <td colSpan={6}>
                          <div className="empty-inline">No documents match this view.</div>
                        </td>
                      </tr>
                    ) : (
                      filteredDocuments.map((document) => (
                        <tr
                          key={document.id}
                          className={document.id === selectedDocumentId ? "selected-row" : ""}
                        >
                          <td>
                            <div className="name">{document.display_name}</div>
                            <div className="muted num table-sub">
                              {document.current_version
                                ? `${formatBytes(document.current_version.byte_size)} · sha256 ${shortHash(
                                    document.current_version.sha256,
                                  )}`
                                : "No parsed version"}
                            </div>
                          </td>
                          <td>
                            <StatusBadge status={document.current_version?.status ?? "failed"} />
                          </td>
                          <td className="num">
                            {document.current_version?.page_count ??
                              document.current_version?.line_count ??
                              "—"}
                          </td>
                          <td className="num">{document.current_version?.chunk_count ?? "—"}</td>
                          <td className="muted">
                            {document.current_version
                              ? formatDate(document.current_version.created_at)
                              : "—"}
                          </td>
                          <td>
                            <button
                              className="btn btn-sm btn-ghost"
                              type="button"
                              onClick={() => setSelectedDocumentId(document.id)}
                            >
                              Inspect
                            </button>
                          </td>
                        </tr>
                      ))
                    )}
                  </tbody>
                </table>
              </div>

              <SelectedDocumentCard
                selectedDocument={selectedDocument}
                inspection={inspection}
                busy={busy}
                onReprocess={() => void reprocessSelected()}
                onDelete={() => void deleteSelected()}
              />
            </div>

            {inspection && selectedChunk ? (
              <>
                <div className="banner banner-accent source-banner">
                  <div>
                    <strong>Source Viewer</strong>
                    <span>
                      This is what retrieval sees: parsed text, chunk boundaries, and metadata
                      attached to each chunk.
                    </span>
                  </div>
                </div>
                <div className="viewer">
                  <aside className="card card-pad-sm tree">
                    <div className="eyebrow">Structure</div>
                    <details open>
                      <summary>Sections ({inspection.version.section_count})</summary>
                      {sectionNames(inspection.chunks).map((section) => (
                        <span className="leaf" key={section}>
                          {section}
                        </span>
                      ))}
                    </details>
                    <details open>
                      <summary>Pages / lines</summary>
                      <span className="leaf">
                        {inspection.version.page_count
                          ? `${inspection.version.page_count} pages`
                          : `${inspection.version.line_count ?? 0} lines`}
                      </span>
                    </details>
                    <details open>
                      <summary>Chunks ({inspection.chunks.length})</summary>
                      {inspection.chunks.map((chunk) => (
                        <button
                          type="button"
                          key={chunk.id}
                          className={chunk.id === selectedChunk.id ? "leaf active" : "leaf"}
                          onClick={() => setSelectedChunkId(chunk.id)}
                        >
                          chunk {chunk.chunk_index + 1} · {provenanceLabel(chunk)}
                        </button>
                      ))}
                    </details>
                  </aside>

                  <section className="card doc-text">
                    <div className="page-break">
                      {provenanceLabel(selectedChunk)}
                      {selectedChunk.section ? ` · ${selectedChunk.section}` : ""}
                    </div>
                    {inspection.chunks.slice(0, 3).map((chunk) =>
                      chunk.id === selectedChunk.id ? (
                        <div className="chunk-mark" key={chunk.id}>
                          <div className="muted num chunk-label">
                            chunk {chunk.chunk_index + 1} · {provenanceLabel(chunk)}
                            {chunk.char_start !== null && chunk.char_end !== null
                              ? ` · offsets ${chunk.char_start}-${chunk.char_end}`
                              : ""}
                          </div>
                          {chunk.text}
                        </div>
                      ) : (
                        <p key={chunk.id}>{chunk.text}</p>
                      ),
                    )}
                    {inspection.chunks.length > 3 && (
                      <p className="hint">Select another chunk in the structure pane to inspect it.</p>
                    )}
                  </section>

                  <aside className="card card-pad-sm">
                    <div className="eyebrow">Selected chunk</div>
                    <h2>chunk {selectedChunk.chunk_index + 1}</h2>
                    <dl className="kv">
                      <dt>repository</dt>
                      <dd>{repository?.name ?? "default"}</dd>
                      <dt>document</dt>
                      <dd>{inspection.document.id}</dd>
                      <dt>version</dt>
                      <dd>{inspection.version.id}</dd>
                      <dt>page/line</dt>
                      <dd>{provenanceLabel(selectedChunk)}</dd>
                      <dt>section</dt>
                      <dd>{selectedChunk.section ?? "—"}</dd>
                      <dt>chunk index</dt>
                      <dd>
                        {selectedChunk.chunk_index + 1} / {inspection.version.chunk_count}
                      </dd>
                      <dt>parser</dt>
                      <dd>{inspection.version.parser_version}</dd>
                      <dt>source type</dt>
                      <dd>{inspection.version.source_type}</dd>
                    </dl>
                    {inspection.version.warnings.length > 0 && (
                      <>
                        <hr className="divider" />
                        <div className="banner banner-warn">
                          <div>{inspection.version.warnings.join(" ")}</div>
                        </div>
                      </>
                    )}
                    <p className="hint citation">
                      Citation: [{inspection.document.display_name}, {provenanceLabel(selectedChunk)},
                      chunk {selectedChunk.chunk_index + 1}]
                    </p>
                  </aside>
                </div>
              </>
            ) : (
              <div className="empty">
                <h3>Select a document</h3>
                <p>Uploaded documents will open in the source viewer with chunks and provenance.</p>
              </div>
            )}
          </div>
        </main>
      </div>
    </>
  );
}

function SelectedDocumentCard({
  selectedDocument,
  inspection,
  busy,
  onReprocess,
  onDelete,
}: {
  selectedDocument: DocumentSummary | null;
  inspection: Inspection | null;
  busy: boolean;
  onReprocess: () => void;
  onDelete: () => void;
}) {
  const version = selectedDocument?.current_version ?? null;
  if (!selectedDocument || !version) {
    return (
      <div className="card card-pad-sm">
        <div className="eyebrow">Selected document</div>
        <p className="muted">No document selected.</p>
      </div>
    );
  }

  return (
    <div className="card card-pad-sm">
      <div className="eyebrow">Selected document</div>
      <h2>{selectedDocument.display_name}</h2>
      <dl className="kv selected-kv">
        <dt>Status</dt>
        <dd>{version.status}</dd>
        <dt>Pages / lines</dt>
        <dd>{version.page_count ?? version.line_count ?? "—"}</dd>
        <dt>Sections</dt>
        <dd>{version.section_count}</dd>
        <dt>Chunks</dt>
        <dd>{version.chunk_count}</dd>
        <dt>Parser</dt>
        <dd>{version.parser_version}</dd>
        <dt>Hash</dt>
        <dd>{shortHash(version.sha256)}</dd>
      </dl>
      {versionSummary(version) && (
        <>
          <hr className="divider" />
          <div className={version.ocr_required ? "banner banner-warn" : "banner banner-accent"}>
            <div>{versionSummary(version)}</div>
          </div>
        </>
      )}
      <div className="stack selected-actions">
        <a className="btn btn-primary" href="#source-viewer">
          Open in Source Viewer
        </a>
        <button className="btn" type="button" onClick={onReprocess} disabled={busy || !inspection}>
          Reprocess
        </button>
        <button className="btn btn-ghost danger-action" type="button" onClick={onDelete} disabled={busy}>
          Delete
        </button>
      </div>
    </div>
  );
}

function StatusBadge({ status }: { status: DocumentVersion["status"] }) {
  const className =
    status === "parsed"
      ? "badge badge-ok"
      : status === "needs_ocr"
        ? "badge badge-warn"
        : status === "failed"
          ? "badge badge-danger"
          : "badge";
  return (
    <span className={className}>
      <span className="dot" />
      {status.replace("_", " ")}
    </span>
  );
}

function versionSummary(version: DocumentVersion) {
  const hints = version.metadata.patent_section_hints;
  if (Array.isArray(hints) && hints.length > 0) {
    return `Patent PDF hints: ${hints.join(", ")}`;
  }
  if (version.ocr_required) {
    return "This document has little extractable text and should be inspected with OCR/page images.";
  }
  if (version.warnings.length > 0) {
    return version.warnings.join(" ");
  }
  return `${version.parser_version} produced inspectable source chunks.`;
}

function provenanceLabel(chunk: Chunk) {
  if (chunk.page_start) {
    return `p. ${chunk.page_start}${chunk.page_end && chunk.page_end !== chunk.page_start ? `-${chunk.page_end}` : ""}`;
  }
  if (chunk.line_start) {
    return `lines ${chunk.line_start}${chunk.line_end && chunk.line_end !== chunk.line_start ? `-${chunk.line_end}` : ""}`;
  }
  return chunk.section ?? "document";
}

function sectionNames(chunks: Chunk[]) {
  const sections = chunks
    .map((chunk) => chunk.section)
    .filter((section): section is string => Boolean(section));
  return Array.from(new Set(sections)).slice(0, 12);
}

function shortHash(hash: string) {
  return hash.length > 12 ? `${hash.slice(0, 4)}…${hash.slice(-4)}` : hash;
}

function formatBytes(bytes: number) {
  if (bytes < 1024) {
    return `${bytes} B`;
  }
  if (bytes < 1024 * 1024) {
    return `${(bytes / 1024).toFixed(1)} KB`;
  }
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

function formatDate(value: string) {
  return new Intl.DateTimeFormat(undefined, { month: "short", day: "numeric" }).format(
    new Date(value),
  );
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
