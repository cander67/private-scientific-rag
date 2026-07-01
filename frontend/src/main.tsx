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
  original_filename: string;
  chunk_count: number;
  page_count: number | null;
  line_count: number | null;
  section_count: number;
  ocr_required: boolean;
  warnings: string[];
  metadata: Record<string, unknown>;
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

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
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
    <main className="app-shell">
      <header className="topbar">
        <div>
          <span className="eyebrow">Private Scientific RAG</span>
          <h1>Documents</h1>
        </div>
        <div className="repo-status">
          <span>{repository?.name ?? "No repository"}</span>
          <strong>{message}</strong>
        </div>
      </header>

      <section className="toolbar" aria-label="Document actions">
        <label className="file-picker">
          <input
            type="file"
            multiple
            accept=".pdf,.txt,.md,.markdown,.ann,application/pdf,text/plain,text/markdown"
            onChange={(event) => void uploadFiles(event.target.files)}
            disabled={busy || !repository}
          />
          <span>Upload</span>
        </label>
        <button type="button" onClick={() => void reprocessSelected()} disabled={busy || !selectedDocument}>
          Reprocess
        </button>
        <button type="button" onClick={() => void deleteSelected()} disabled={busy || !selectedDocument}>
          Delete
        </button>
      </section>

      <section className="workspace">
        <aside className="document-list" aria-label="Uploaded documents">
          {documents.length === 0 ? (
            <div className="empty-state">No documents uploaded</div>
          ) : (
            documents.map((document) => (
              <button
                type="button"
                key={document.id}
                className={document.id === selectedDocumentId ? "document-row active" : "document-row"}
                onClick={() => setSelectedDocumentId(document.id)}
              >
                <span>{document.display_name}</span>
                <small>{document.current_version?.status ?? "pending"}</small>
              </button>
            ))
          )}
        </aside>

        <section className="inspector" aria-label="Source inspector">
          {inspection ? (
            <>
              <div className="inspector-header">
                <div>
                  <h2>{inspection.document.display_name}</h2>
                  <p>{versionSummary(inspection.version)}</p>
                </div>
                <StatusBadge status={inspection.version.status} />
              </div>

              <div className="metadata-grid">
                <Metric label="Type" value={inspection.version.source_type} />
                <Metric label="Chunks" value={String(inspection.version.chunk_count)} />
                <Metric label="Sections" value={String(inspection.version.section_count)} />
                <Metric
                  label={inspection.version.page_count ? "Pages" : "Lines"}
                  value={String(inspection.version.page_count ?? inspection.version.line_count ?? 0)}
                />
              </div>

              {inspection.version.warnings.length > 0 && (
                <div className="warning-list">
                  {inspection.version.warnings.map((warning) => (
                    <span key={warning}>{warning}</span>
                  ))}
                </div>
              )}

              <div className="chunk-list">
                {inspection.chunks.map((chunk) => (
                  <article className="chunk-row" key={chunk.id}>
                    <div className="chunk-meta">
                      <strong>Chunk {chunk.chunk_index + 1}</strong>
                      <span>{provenanceLabel(chunk)}</span>
                    </div>
                    <p>{chunk.text}</p>
                  </article>
                ))}
              </div>
            </>
          ) : (
            <div className="empty-state">Select a document to inspect</div>
          )}
        </section>
      </section>
    </main>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusBadge({ status }: { status: DocumentVersion["status"] }) {
  return <span className={`status-badge ${status}`}>{status.replace("_", " ")}</span>;
}

function versionSummary(version: DocumentVersion) {
  const hints = version.metadata.patent_section_hints;
  if (Array.isArray(hints) && hints.length > 0) {
    return `Patent PDF hints: ${hints.join(", ")}`;
  }
  if (version.ocr_required) {
    return "Page image inspection recommended";
  }
  return `${version.parser_name ?? "Parser"} produced inspectable source chunks`;
}

function provenanceLabel(chunk: Chunk) {
  if (chunk.page_start) {
    return `page ${chunk.page_start}${chunk.page_end && chunk.page_end !== chunk.page_start ? `-${chunk.page_end}` : ""}`;
  }
  if (chunk.line_start) {
    return `lines ${chunk.line_start}${chunk.line_end && chunk.line_end !== chunk.line_start ? `-${chunk.line_end}` : ""}`;
  }
  return chunk.section ?? "document";
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
