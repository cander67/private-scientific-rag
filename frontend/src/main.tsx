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

type View = "documents" | "source" | "search" | "chat";

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
  source_hash: string;
  metadata: Record<string, unknown>;
};

type PageImage = {
  page: number;
  url: string;
  mime_type: string;
  width: number | null;
  height: number | null;
  byte_size: number;
  sha256: string;
};

type Inspection = {
  document: DocumentSummary;
  version: DocumentVersion;
  chunks: Chunk[];
  page_images: PageImage[];
};

type FullTextRebuildResponse = {
  repository_id: string;
  indexed_chunks: number;
  tokenizer: "unicode61" | "porter";
};

type VectorRebuildResponse = {
  repository_id: string;
  embedding_run_id: string;
  provider: string;
  model: string;
  collection_name: string;
  indexed_chunks: number;
  vector_size: number;
  distance: "cosine" | "dot" | "euclid";
};

type HybridRebuildResponse = {
  repository_id: string;
  indexed_chunks: number;
  model: string;
};

type SearchMode = "full-text" | "vector" | "hybrid";
type RerankerStrategy = "none" | "cross_encoder" | "metadata_boost" | "cross_encoder_metadata_boost";
type BoostLevel = "low" | "medium" | "high";
type SearchRebuildResponse = FullTextRebuildResponse | VectorRebuildResponse | HybridRebuildResponse;

type FullTextSearchResult = {
  mode: "full-text";
  rank: number;
  score: number;
  repository_id: string;
  document_id: string;
  document_version_id: string;
  chunk_id: string;
  chunk_index: number;
  document_title: string;
  section: string | null;
  page_start: number | null;
  page_end: number | null;
  line_start: number | null;
  line_end: number | null;
  snippet: string;
  matched_fields: string[];
  metadata: {
    source_type?: string;
    document_kind?: string | null;
    tags?: string[];
    has_table?: boolean;
    has_figure?: boolean;
    patent_sections?: string[];
  };
};

type VectorSearchResult = {
  mode: "vector";
  rank: number;
  score: number;
  distance: "cosine" | "dot" | "euclid";
  repository_id: string;
  document_id: string;
  document_version_id: string;
  chunk_id: string;
  chunk_index: number;
  document_title: string;
  section: string | null;
  page_start: number | null;
  page_end: number | null;
  line_start: number | null;
  line_end: number | null;
  text_preview: string;
  metadata: {
    source_type?: string;
    document_kind?: string | null;
    tags?: string[];
    has_table?: boolean;
    has_figure?: boolean;
    patent_sections?: string[];
  };
  embedding_run_id: string;
  embedding_provider: string;
  embedding_model: string;
  vector_size: number;
  collection_name: string;
};

type RetrievalSearchResult = {
  mode: SearchMode;
  rank: number;
  final_score: number;
  score_breakdown: {
    bm25?: number | null;
    dense?: number | null;
    rrf?: number | null;
    rerank?: number | null;
    metadata_boost?: number | null;
  };
  source_ranks: {
    full_text?: number | null;
    vector?: number | null;
  };
  repository_id: string;
  document_id: string;
  document_version_id: string;
  chunk_id: string;
  chunk_index: number;
  document_title: string;
  section: string | null;
  page_start: number | null;
  page_end: number | null;
  line_start: number | null;
  line_end: number | null;
  snippet?: string | null;
  text_preview?: string | null;
  matched_fields: string[];
  metadata: {
    source_type?: string;
    document_kind?: string | null;
    tags?: string[];
    has_table?: boolean;
    has_figure?: boolean;
    patent_sections?: string[];
  };
  embedding_run_id?: string | null;
  embedding_provider?: string | null;
  embedding_model?: string | null;
  vector_size?: number | null;
  collection_name?: string | null;
};

type SearchResult = RetrievalSearchResult;

type FullTextSearchResponse = {
  query: string;
  normalized_query: string;
  repository_id: string;
  results: FullTextSearchResult[];
};

type VectorSearchResponse = {
  query: string;
  repository_id: string;
  embedding_run_id: string;
  provider: string;
  model: string;
  collection_name: string;
  vector_size: number;
  distance: string;
  results: VectorSearchResult[];
};

type RetrievalSearchResponse = {
  run_id: string;
  query: string;
  repository_id: string;
  mode: "full_text" | "vector" | "hybrid";
  top_k: number;
  candidate_pool_size: number;
  rrf_constant: number;
  reranker_strategy: RerankerStrategy;
  results: RetrievalSearchResult[];
};

type ChatCitation = {
  citation_id: number;
  token: string;
  document_id: string;
  document_version_id: string;
  chunk_id: string;
  chunk_index: number;
  document_title: string;
  section: string | null;
  page_start: number | null;
  page_end: number | null;
  line_start: number | null;
  line_end: number | null;
  metadata: {
    source_type?: string;
    document_kind?: string | null;
    tags?: string[];
    has_table?: boolean;
    has_figure?: boolean;
    patent_sections?: string[];
  };
  retrieval_rank: number;
  score_breakdown: Record<string, number | null>;
};

type ChatMessage = {
  id: string;
  session_id: string;
  sequence: number;
  role: "user" | "assistant";
  content: string;
  retrieval_run_id: string | null;
  citations: ChatCitation[];
  created_at: string;
};

type ChatSession = {
  id: string;
  repository_id: string;
  title: string;
  model: string;
  retrieval_settings: {
    mode?: string;
    top_k?: number;
    reranker_strategy?: string;
  };
  prompt_id: string;
  created_at: string;
  updated_at: string;
  messages: ChatMessage[];
};

type ChatQuestionResponse = {
  session: ChatSession;
  user_message: ChatMessage;
  assistant_message: ChatMessage;
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
  const [activeView, setActiveView] = useState<View>(() => viewFromHash(window.location.hash));
  const [searchQuery, setSearchQuery] = useState("LiFePO4");
  const [searchLimit, setSearchLimit] = useState(10);
  const [searchDocumentId, setSearchDocumentId] = useState("");
  const [searchSection, setSearchSection] = useState("");
  const [searchSourceType, setSearchSourceType] = useState("");
  const [searchDocumentKind, setSearchDocumentKind] = useState("");
  const [searchHasTable, setSearchHasTable] = useState(false);
  const [searchHasFigure, setSearchHasFigure] = useState(false);
  const [searchPatentSection, setSearchPatentSection] = useState("");
  const [searchMode, setSearchMode] = useState<SearchMode>("full-text");
  const [rerankerStrategy, setRerankerStrategy] = useState<RerankerStrategy>("none");
  const [candidatePoolSize, setCandidatePoolSize] = useState(50);
  const [rrfConstant, setRrfConstant] = useState(60);
  const [metadataBoostLevel, setMetadataBoostLevel] = useState<BoostLevel>("medium");
  const [searchResults, setSearchResults] = useState<SearchResult[]>([]);
  const [searchBusy, setSearchBusy] = useState(false);
  const [searchMessage, setSearchMessage] = useState("Rebuild the full-text index, then run a query.");
  const [lastRebuild, setLastRebuild] = useState<SearchRebuildResponse | null>(null);
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([]);
  const [activeChatSessionId, setActiveChatSessionId] = useState<string | null>(null);
  const [chatInput, setChatInput] = useState("");
  const [chatBusy, setChatBusy] = useState(false);
  const [chatMessage, setChatMessage] = useState("Create a chat session or ask a question.");
  const [activeCitation, setActiveCitation] = useState<ChatCitation | null>(null);

  useEffect(() => {
    const onHashChange = () => setActiveView(viewFromHash(window.location.hash));
    window.addEventListener("hashchange", onHashChange);
    return () => window.removeEventListener("hashchange", onHashChange);
  }, []);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
  }, [theme]);

  useEffect(() => {
    void loadRepository();
  }, []);

  useEffect(() => {
    if (repository) {
      void loadDocuments(repository.id);
      void loadChatSessions(repository.id);
    }
  }, [repository]);

  useEffect(() => {
    if (repository && selectedDocumentId) {
      void inspectDocument(repository.id, selectedDocumentId);
    }
  }, [repository, selectedDocumentId]);

  useEffect(() => {
    setSelectedChunkId((current) =>
      current && inspection?.chunks.some((chunk) => chunk.id === current)
        ? current
        : (inspection?.chunks[0]?.id ?? null),
    );
  }, [inspection]);

  const selectedDocument = useMemo(
    () => documents.find((document) => document.id === selectedDocumentId) ?? null,
    [documents, selectedDocumentId],
  );

  const selectedChunk = useMemo(
    () => inspection?.chunks.find((chunk) => chunk.id === selectedChunkId) ?? inspection?.chunks[0] ?? null,
    [inspection, selectedChunkId],
  );

  const activeChatSession = useMemo(
    () => chatSessions.find((chatSession) => chatSession.id === activeChatSessionId) ?? chatSessions[0] ?? null,
    [chatSessions, activeChatSessionId],
  );

  const contextChunks = useMemo(() => {
    if (!inspection || !selectedChunk) {
      return [];
    }
    return chunkContextWindow(inspection.chunks, selectedChunk.id);
  }, [inspection, selectedChunk]);

  const selectedPageImages = useMemo(() => {
    if (!inspection || !selectedChunk?.page_start) {
      return inspection?.page_images.slice(0, 3) ?? [];
    }
    const pageEnd = selectedChunk.page_end ?? selectedChunk.page_start;
    return inspection.page_images.filter(
      (image) => image.page >= selectedChunk.page_start! && image.page <= pageEnd,
    );
  }, [inspection, selectedChunk]);

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

  async function loadChatSessions(repositoryId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/chat/sessions`);
      if (!response.ok) {
        throw new Error("chat sessions unavailable");
      }
      const payload = (await response.json()) as ChatSession[];
      setChatSessions(payload);
      setActiveChatSessionId((current) => current ?? payload[0]?.id ?? null);
      setChatMessage(payload.length > 0 ? "Ready" : "No chat sessions yet");
    } catch {
      setChatMessage("Could not load chat sessions");
    }
  }

  async function createChatSession() {
    if (!repository) {
      return null;
    }
    setChatBusy(true);
    setChatMessage("Creating chat session");
    try {
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ title: "Repository chat" }),
      });
      if (!response.ok) {
        throw new Error("create chat failed");
      }
      const payload = (await response.json()) as ChatSession;
      setChatSessions((current) => [payload, ...current]);
      setActiveChatSessionId(payload.id);
      setChatMessage("Ready");
      return payload;
    } catch {
      setChatMessage("Could not create chat session");
      return null;
    } finally {
      setChatBusy(false);
    }
  }

  async function askChatQuestion() {
    if (!repository || !chatInput.trim()) {
      return;
    }
    const content = chatInput.trim();
    setChatBusy(true);
    setChatInput("");
    setChatMessage("Retrieving context and asking the local model");
    try {
      const chatSession = activeChatSession ?? (await createChatSession());
      if (!chatSession) {
        throw new Error("missing chat session");
      }
      const response = await fetch(
        `${API_BASE}/repositories/${repository.id}/chat/sessions/${chatSession.id}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content }),
        },
      );
      if (!response.ok) {
        throw new Error("chat question failed");
      }
      const payload = (await response.json()) as ChatQuestionResponse;
      setChatSessions((current) =>
        current.map((session) => (session.id === payload.session.id ? payload.session : session)),
      );
      setActiveChatSessionId(payload.session.id);
      setChatMessage(
        `${payload.assistant_message.citations.length} citations · run ${
          payload.assistant_message.retrieval_run_id?.slice(0, 8) ?? "local"
        }`,
      );
    } catch {
      setChatInput(content);
      setChatMessage("Chat failed. Check indexes, reranker model, and Ollama setup.");
    } finally {
      setChatBusy(false);
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

  async function rebuildSearchIndex() {
    if (!repository) {
      return;
    }
    setSearchBusy(true);
    setSearchMessage(`Rebuilding ${searchModeLabel(searchMode)} index`);
    try {
      if (searchMode === "hybrid") {
        const sparseResponse = await fetch(`${API_BASE}/repositories/${repository.id}/full-text/rebuild`, {
          method: "POST",
        });
        const vectorResponse = await fetch(`${API_BASE}/repositories/${repository.id}/vector/rebuild`, {
          method: "POST",
        });
        if (!sparseResponse.ok || !vectorResponse.ok) {
          throw new Error("hybrid rebuild failed");
        }
        const sparsePayload = (await sparseResponse.json()) as FullTextRebuildResponse;
        const vectorPayload = (await vectorResponse.json()) as VectorRebuildResponse;
        setLastRebuild({
          repository_id: repository.id,
          indexed_chunks: Math.max(sparsePayload.indexed_chunks, vectorPayload.indexed_chunks),
          model: vectorPayload.model,
        });
        setSearchMessage(`Indexed ${vectorPayload.indexed_chunks} vector chunks`);
      } else {
        const endpoint = searchMode === "vector" ? "vector" : "full-text";
        const response = await fetch(`${API_BASE}/repositories/${repository.id}/${endpoint}/rebuild`, {
          method: "POST",
        });
        if (!response.ok) {
          throw new Error("rebuild failed");
        }
        const payload = (await response.json()) as SearchRebuildResponse;
        setLastRebuild(payload);
        setSearchMessage(`Indexed ${payload.indexed_chunks} chunks`);
      }
    } catch {
      setSearchMessage(`${searchModeLabel(searchMode)} rebuild failed`);
    } finally {
      setSearchBusy(false);
    }
  }

  async function runSearch() {
    if (!repository || !searchQuery.trim()) {
      return;
    }
    setSearchBusy(true);
    setSearchMessage(`Searching ${searchModeLabel(searchMode)} index`);
    try {
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/retrieval/search`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: searchQuery,
          mode: apiSearchMode(searchMode),
          top_k: searchLimit,
          candidate_pool_size: candidatePoolSize,
          rrf_constant: rrfConstant,
          reranker_strategy: rerankerStrategy,
          metadata_boosts: {
            section: metadataBoostLevel,
            patent_section: metadataBoostLevel,
            document_kind: metadataBoostLevel,
            table_figure: metadataBoostLevel,
          },
          filters: {
            document_id: searchDocumentId || null,
            section: searchSection || null,
            source_type: searchSourceType || null,
            document_kind: searchDocumentKind || null,
            has_table: searchHasTable ? true : null,
            has_figure: searchHasFigure ? true : null,
            patent_section: searchPatentSection || null,
          },
        }),
      });
      if (!response.ok) {
        throw new Error("search failed");
      }
      const payload = (await response.json()) as RetrievalSearchResponse;
      setSearchResults(payload.results.map((result) => ({ ...result, mode: searchMode })));
      setSearchMessage(`${payload.results.length} results · run ${payload.run_id.slice(0, 8)}`);
    } catch {
      setSearchMessage(`${searchModeLabel(searchMode)} search failed. Rebuild the index and try again.`);
      setSearchResults([]);
    } finally {
      setSearchBusy(false);
    }
  }

  function navigateTo(view: View) {
    window.location.hash =
      view === "documents"
        ? "documents"
        : view === "source"
          ? "source-viewer"
          : view === "chat"
            ? "chat-workspace"
            : "search-lab";
    setActiveView(view);
    setNavOpen(false);
  }

  function openSearchResult(result: SearchResult) {
    setSelectedDocumentId(result.document_id);
    setSelectedChunkId(result.chunk_id);
    navigateTo("source");
  }

  function openChatCitation(citation: ChatCitation) {
    setSelectedDocumentId(citation.document_id);
    setSelectedChunkId(citation.chunk_id);
    setActiveCitation(null);
    navigateTo("source");
  }

  const title =
    activeView === "search"
      ? "Search Lab"
      : activeView === "source"
        ? "Source Viewer"
        : activeView === "chat"
          ? "Chat Workspace"
          : "Document Manager";
  const subtitle =
    activeView === "search"
      ? "Inspect full-text retrieval with BM25 scores and citation provenance"
      : activeView === "chat"
        ? `${repository?.name ?? "Default Repository"} · ${activeChatSession?.model ?? "local model"} · ${chatMessage}`
      : `${repository?.name ?? "Default Repository"} · ${message}`;

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
            <a
              className={activeView === "documents" ? "active" : ""}
              href="#documents"
              onClick={() => navigateTo("documents")}
            >
              Document Manager
            </a>
            <a
              className={activeView === "source" ? "active" : ""}
              href="#source-viewer"
              onClick={() => navigateTo("source")}
            >
              Source Viewer
            </a>
            <a
              className={activeView === "search" ? "active" : ""}
              href="#search-lab"
              onClick={() => navigateTo("search")}
            >
              Search Lab
            </a>
            <a>Prompt Sandbox</a>
            <a
              className={activeView === "chat" ? "active" : ""}
              href="#chat-workspace"
              onClick={() => navigateTo("chat")}
            >
              Chat Workspace
            </a>
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
                <h1>{title}</h1>
                <p>{subtitle}</p>
              </div>
            </div>
            <div className="topbar-actions">
              {activeView === "documents" && (
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
              )}
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
            {activeView === "search" ? (
              <SearchLab
                documents={documents}
                repositoryReady={Boolean(repository)}
                mode={searchMode}
                rerankerStrategy={rerankerStrategy}
                candidatePoolSize={candidatePoolSize}
                rrfConstant={rrfConstant}
                metadataBoostLevel={metadataBoostLevel}
                query={searchQuery}
                limit={searchLimit}
                documentId={searchDocumentId}
                section={searchSection}
                sourceType={searchSourceType}
                documentKind={searchDocumentKind}
                hasTable={searchHasTable}
                hasFigure={searchHasFigure}
                patentSection={searchPatentSection}
                results={searchResults}
                busy={searchBusy}
                message={searchMessage}
                lastRebuild={lastRebuild}
                onModeChange={(mode) => {
                  setSearchMode(mode);
                  setSearchResults([]);
                  setLastRebuild(null);
                  setSearchMessage(`Rebuild the ${searchModeLabel(mode)} index, then run a query.`);
                }}
                onRerankerStrategyChange={setRerankerStrategy}
                onCandidatePoolSizeChange={setCandidatePoolSize}
                onRrfConstantChange={setRrfConstant}
                onMetadataBoostLevelChange={setMetadataBoostLevel}
                onQueryChange={setSearchQuery}
                onLimitChange={setSearchLimit}
                onDocumentChange={setSearchDocumentId}
                onSectionChange={setSearchSection}
                onSourceTypeChange={setSearchSourceType}
                onDocumentKindChange={setSearchDocumentKind}
                onHasTableChange={setSearchHasTable}
                onHasFigureChange={setSearchHasFigure}
                onPatentSectionChange={setSearchPatentSection}
                onRebuild={() => void rebuildSearchIndex()}
                onSearch={() => void runSearch()}
                onOpenResult={openSearchResult}
              />
            ) : activeView === "chat" ? (
              <ChatWorkspace
                sessions={chatSessions}
                activeSession={activeChatSession}
                input={chatInput}
                busy={chatBusy}
                message={chatMessage}
                activeCitation={activeCitation}
                onInputChange={setChatInput}
                onCreateSession={() => void createChatSession()}
                onSelectSession={setActiveChatSessionId}
                onAsk={() => void askChatQuestion()}
                onCitationClick={setActiveCitation}
                onCloseCitation={() => setActiveCitation(null)}
                onOpenCitation={openChatCitation}
              />
            ) : (
              <>
                {activeView === "documents" && (
                  <>
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
                      <p className="muted">
                        or use the Upload button. Duplicate files are skipped by hash.
                      </p>
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
                                      onClick={() => {
                                        setSelectedDocumentId(document.id);
                                        navigateTo("source");
                                      }}
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
                  </>
                )}

                {activeView === "source" && (inspection ? (
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
                      <summary>Page images ({inspection.page_images.length})</summary>
                      {inspection.page_images.length > 0 ? (
                        inspection.page_images.slice(0, 24).map((image) => (
                          <a className="leaf" key={image.page} href={absoluteApiUrl(image.url)}>
                            page {image.page}
                          </a>
                        ))
                      ) : (
                        <span className="leaf">No thumbnails</span>
                      )}
                    </details>
                    <details open>
                      <summary>Chunks ({inspection.chunks.length})</summary>
                      {inspection.chunks.length > 0 ? (
                        inspection.chunks.map((chunk) => (
                          <button
                            type="button"
                            key={chunk.id}
                            className={chunk.id === selectedChunk?.id ? "leaf active" : "leaf"}
                            onClick={() => setSelectedChunkId(chunk.id)}
                          >
                            chunk {chunk.chunk_index + 1} · {provenanceLabel(chunk)}
                          </button>
                        ))
                      ) : (
                        <span className="leaf">No parsed chunks</span>
                      )}
                    </details>
                  </aside>

                  <section className="card doc-text">
                    {inspection.version.source_type === "pdf" && (
                      <PageImageStrip
                        images={selectedPageImages}
                        pageCount={inspection.version.page_count ?? 0}
                      />
                    )}
                    {selectedChunk ? (
                      <>
                        <div className="page-break">
                          {provenanceLabel(selectedChunk)}
                          {selectedChunk.section ? ` · ${selectedChunk.section}` : ""}
                        </div>
                        {contextChunks.map((chunk) =>
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
                        {inspection.chunks.length > contextChunks.length && (
                          <p className="hint">
                            Showing surrounding chunk context. Select another chunk in the structure
                            pane to move this window.
                          </p>
                        )}
                      </>
                    ) : (
                      <div className="empty-inline">
                        <h3>No parsed chunks yet</h3>
                        <p>
                          Page thumbnails and parser warnings are available for inspection, but this
                          document has no chunk text yet.
                        </p>
                      </div>
                    )}
                  </section>

                  <aside className="card card-pad-sm">
                    <div className="eyebrow">{selectedChunk ? "Selected chunk" : "Document"}</div>
                    <h2>
                      {selectedChunk
                        ? `chunk ${selectedChunk.chunk_index + 1}`
                        : inspection.document.display_name}
                    </h2>
                    {selectedChunk ? (
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
                        <dt>source hash</dt>
                        <dd>{shortHash(selectedChunk.source_hash)}</dd>
                        <dt>offsets</dt>
                        <dd>{offsetLabel(selectedChunk)}</dd>
                        <dt>source type</dt>
                        <dd>{inspection.version.source_type}</dd>
                      </dl>
                    ) : (
                      <dl className="kv">
                        <dt>repository</dt>
                        <dd>{repository?.name ?? "default"}</dd>
                        <dt>document</dt>
                        <dd>{inspection.document.id}</dd>
                        <dt>version</dt>
                        <dd>{inspection.version.id}</dd>
                        <dt>status</dt>
                        <dd>{inspection.version.status}</dd>
                        <dt>parser</dt>
                        <dd>{inspection.version.parser_version}</dd>
                        <dt>source hash</dt>
                        <dd>{shortHash(inspection.version.sha256)}</dd>
                        <dt>source type</dt>
                        <dd>{inspection.version.source_type}</dd>
                      </dl>
                    )}
                    {inspection.version.warnings.length > 0 && (
                      <>
                        <hr className="divider" />
                        <div className="banner banner-warn">
                          <div>{inspection.version.warnings.join(" ")}</div>
                        </div>
                      </>
                    )}
                    {selectedChunk && (
                      <p className="hint citation">
                        Citation: [{inspection.document.display_name},{" "}
                        {provenanceLabel(selectedChunk)}, chunk {selectedChunk.chunk_index + 1}]
                      </p>
                    )}
                  </aside>
                </div>
              </>
            ) : (
              <div className="empty">
                <h3>Select a document</h3>
                <p>Uploaded documents will open in the source viewer with chunks and provenance.</p>
              </div>
            ))}
              </>
            )}
          </div>
        </main>
      </div>
    </>
  );
}

function ChatWorkspace({
  sessions,
  activeSession,
  input,
  busy,
  message,
  activeCitation,
  onInputChange,
  onCreateSession,
  onSelectSession,
  onAsk,
  onCitationClick,
  onCloseCitation,
  onOpenCitation,
}: {
  sessions: ChatSession[];
  activeSession: ChatSession | null;
  input: string;
  busy: boolean;
  message: string;
  activeCitation: ChatCitation | null;
  onInputChange: (value: string) => void;
  onCreateSession: () => void;
  onSelectSession: (value: string) => void;
  onAsk: () => void;
  onCitationClick: (citation: ChatCitation) => void;
  onCloseCitation: () => void;
  onOpenCitation: (citation: ChatCitation) => void;
}) {
  return (
    <>
      <div className="chat-layout">
        <aside className="card card-pad-sm session-list">
          <div className="row row-between session-head">
            <div className="eyebrow">Sessions</div>
            <button className="btn btn-sm btn-ghost" type="button" onClick={onCreateSession} disabled={busy}>
              New
            </button>
          </div>
          {sessions.length > 0 ? (
            sessions.map((session) => (
              <button
                className={session.id === activeSession?.id ? "session-item active" : "session-item"}
                type="button"
                key={session.id}
                onClick={() => onSelectSession(session.id)}
              >
                <span>{session.title}</span>
                <small>
                  {formatDate(session.updated_at)} · {session.messages.length} msgs
                </small>
              </button>
            ))
          ) : (
            <p className="muted">No saved chats yet.</p>
          )}
        </aside>

        <section className="chat-main">
          <div className="banner banner-accent chat-snapshot">
            <div>
              <strong>Retrieval snapshot</strong>
              <span>
                {activeSession
                  ? `${activeSession.retrieval_settings.mode ?? "hybrid"} · ${
                      activeSession.retrieval_settings.reranker_strategy ?? "cross_encoder"
                    } · top-k ${activeSession.retrieval_settings.top_k ?? 6} · ${
                      activeSession.model
                    }`
                  : "hybrid · cross_encoder · gemma3:4b"}
              </span>
            </div>
          </div>

          <div className="chat-thread">
            {activeSession?.messages.length ? (
              activeSession.messages.map((chatMessage) => (
                <ChatBubble
                  message={chatMessage}
                  key={chatMessage.id}
                  onCitationClick={onCitationClick}
                />
              ))
            ) : (
              <div className="empty-inline">
                <h3>Start a repository chat</h3>
                <p>Questions use fresh hybrid retrieval and cite stored source chunks.</p>
              </div>
            )}
          </div>

          <div className="chat-input">
            <textarea
              rows={2}
              value={input}
              onChange={(event) => onInputChange(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && (event.metaKey || event.ctrlKey)) {
                  onAsk();
                }
              }}
              placeholder="Ask a question grounded in this repository..."
              disabled={busy}
            />
            <button className="btn btn-primary" type="button" onClick={onAsk} disabled={busy || !input.trim()}>
              Send
            </button>
          </div>
          <p className="hint">{message}</p>
        </section>
      </div>

      {activeCitation && (
        <div className="overlay open" role="dialog" aria-modal="true">
          <div className="modal citation-modal">
            <div className="modal-head">
              <div>
                <div className="eyebrow">Citation {activeCitation.token}</div>
                <h2>{activeCitation.document_title}</h2>
              </div>
              <button className="close-x" type="button" onClick={onCloseCitation} aria-label="Close citation">
                x
              </button>
            </div>
            <div className="source-card">
              <div className="meta">
                {citationProvenanceLabel(activeCitation)} · chunk {activeCitation.chunk_index + 1} ·
                retrieval rank {activeCitation.retrieval_rank}
              </div>
              <dl className="kv">
                <dt>document</dt>
                <dd>{activeCitation.document_id}</dd>
                <dt>version</dt>
                <dd>{activeCitation.document_version_id}</dd>
                <dt>chunk</dt>
                <dd>{activeCitation.chunk_id}</dd>
                <dt>section</dt>
                <dd>{activeCitation.section ?? "—"}</dd>
              </dl>
              <div className="row result-meta">
                {activeCitation.metadata.source_type && (
                  <span className="badge">{activeCitation.metadata.source_type}</span>
                )}
                {activeCitation.metadata.document_kind && (
                  <span className="badge">{activeCitation.metadata.document_kind}</span>
                )}
                {activeCitation.metadata.has_table && <span className="badge">table</span>}
                {activeCitation.metadata.has_figure && <span className="badge">figure</span>}
              </div>
            </div>
            <div className="row modal-actions">
              <button className="btn btn-primary" type="button" onClick={() => onOpenCitation(activeCitation)}>
                Open in Source Viewer
              </button>
              <button className="btn btn-ghost" type="button" onClick={onCloseCitation}>
                Close
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}

function ChatBubble({
  message,
  onCitationClick,
}: {
  message: ChatMessage;
  onCitationClick: (citation: ChatCitation) => void;
}) {
  return (
    <div className={message.role === "user" ? "msg user" : "msg assistant"}>
      <p>{message.content}</p>
      {message.citations.length > 0 && (
        <div className="chat-citations">
          {message.citations.map((citation) => (
            <button
              className="cite"
              type="button"
              key={`${message.id}-${citation.citation_id}`}
              onClick={() => onCitationClick(citation)}
              title={`${citation.document_title}, ${citationProvenanceLabel(citation)}`}
            >
              {citation.token}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function SearchLab({
  documents,
  repositoryReady,
  mode,
  rerankerStrategy,
  candidatePoolSize,
  rrfConstant,
  metadataBoostLevel,
  query,
  limit,
  documentId,
  section,
  sourceType,
  documentKind,
  hasTable,
  hasFigure,
  patentSection,
  results,
  busy,
  message,
  lastRebuild,
  onModeChange,
  onRerankerStrategyChange,
  onCandidatePoolSizeChange,
  onRrfConstantChange,
  onMetadataBoostLevelChange,
  onQueryChange,
  onLimitChange,
  onDocumentChange,
  onSectionChange,
  onSourceTypeChange,
  onDocumentKindChange,
  onHasTableChange,
  onHasFigureChange,
  onPatentSectionChange,
  onRebuild,
  onSearch,
  onOpenResult,
}: {
  documents: DocumentSummary[];
  repositoryReady: boolean;
  mode: SearchMode;
  rerankerStrategy: RerankerStrategy;
  candidatePoolSize: number;
  rrfConstant: number;
  metadataBoostLevel: BoostLevel;
  query: string;
  limit: number;
  documentId: string;
  section: string;
  sourceType: string;
  documentKind: string;
  hasTable: boolean;
  hasFigure: boolean;
  patentSection: string;
  results: SearchResult[];
  busy: boolean;
  message: string;
  lastRebuild: SearchRebuildResponse | null;
  onModeChange: (value: SearchMode) => void;
  onRerankerStrategyChange: (value: RerankerStrategy) => void;
  onCandidatePoolSizeChange: (value: number) => void;
  onRrfConstantChange: (value: number) => void;
  onMetadataBoostLevelChange: (value: BoostLevel) => void;
  onQueryChange: (value: string) => void;
  onLimitChange: (value: number) => void;
  onDocumentChange: (value: string) => void;
  onSectionChange: (value: string) => void;
  onSourceTypeChange: (value: string) => void;
  onDocumentKindChange: (value: string) => void;
  onHasTableChange: (value: boolean) => void;
  onHasFigureChange: (value: boolean) => void;
  onPatentSectionChange: (value: string) => void;
  onRebuild: () => void;
  onSearch: () => void;
  onOpenResult: (result: SearchResult) => void;
}) {
  const sections = Array.from(
    new Set(
      documents
        .map((document) => document.current_version?.metadata?.patent_section_hints)
        .filter((hints): hints is unknown[] => Array.isArray(hints))
        .flat()
        .map(String),
    ),
  );
  return (
    <>
      <div className="card search-panel">
        <label className="field" htmlFor="search-query">
          Query
        </label>
        <div className="row search-row">
          <input
            id="search-query"
            type="search"
            value={query}
            onChange={(event) => onQueryChange(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter") {
                onSearch();
              }
            }}
          />
          <button
            className="btn btn-primary"
            type="button"
            onClick={onSearch}
            disabled={busy || !repositoryReady || !query.trim()}
          >
            Run search
          </button>
          <button className="btn" type="button" onClick={onRebuild} disabled={busy || !repositoryReady}>
            Rebuild index
          </button>
        </div>

        <div className="grid grid-2 search-controls">
          <div>
            <label className="field">Search mode</label>
            <div className="segmented">
              <button type="button" aria-pressed={mode === "full-text"} onClick={() => onModeChange("full-text")}>
                Full-text
              </button>
              <button type="button" aria-pressed={mode === "vector"} onClick={() => onModeChange("vector")}>
                Vector
              </button>
              <button type="button" aria-pressed={mode === "hybrid"} onClick={() => onModeChange("hybrid")}>
                Hybrid
              </button>
            </div>
          </div>
          <div>
            <label className="field" htmlFor="reranker-strategy">
              Reranking strategy
            </label>
            <select
              id="reranker-strategy"
              value={rerankerStrategy}
              onChange={(event) => onRerankerStrategyChange(event.target.value as RerankerStrategy)}
            >
              <option value="none">None</option>
              <option value="cross_encoder">Cross-encoder</option>
              <option value="metadata_boost">Metadata boost</option>
              <option value="cross_encoder_metadata_boost">Cross-encoder + metadata boost</option>
              <option disabled>Diversity/MMR - future</option>
            </select>
          </div>
        </div>

        <div className="grid grid-3 search-controls">
          <div>
            <label className="field" htmlFor="search-limit">
              Top-k
            </label>
            <select
              id="search-limit"
              value={limit}
              onChange={(event) => onLimitChange(Number(event.target.value))}
            >
              {[5, 10, 20, 50].map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field" htmlFor="candidate-pool-size">
              Candidate pool
            </label>
            <select
              id="candidate-pool-size"
              value={candidatePoolSize}
              onChange={(event) => onCandidatePoolSizeChange(Number(event.target.value))}
            >
              {[25, 50, 100, 150, 250].map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field" htmlFor="rrf-constant">
              RRF constant
            </label>
            <select
              id="rrf-constant"
              value={rrfConstant}
              onChange={(event) => onRrfConstantChange(Number(event.target.value))}
            >
              {[10, 30, 60, 100].map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field" htmlFor="metadata-boost-level">
              Metadata boost
            </label>
            <select
              id="metadata-boost-level"
              value={metadataBoostLevel}
              onChange={(event) => onMetadataBoostLevelChange(event.target.value as BoostLevel)}
            >
              <option value="low">Low</option>
              <option value="medium">Medium</option>
              <option value="high">High</option>
            </select>
          </div>
          <div>
            <label className="field" htmlFor="search-document">
              Document
            </label>
            <select
              id="search-document"
              value={documentId}
              onChange={(event) => onDocumentChange(event.target.value)}
            >
              <option value="">Any document</option>
              {documents.map((document) => (
                <option value={document.id} key={document.id}>
                  {document.display_name}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label className="field" htmlFor="search-section">
              Section
            </label>
            <input
              id="search-section"
              value={section}
              onChange={(event) => onSectionChange(event.target.value)}
              placeholder="Abstract, Claims, Results"
            />
          </div>
          <div>
            <label className="field" htmlFor="search-source-type">
              Source type
            </label>
            <select
              id="search-source-type"
              value={sourceType}
              onChange={(event) => onSourceTypeChange(event.target.value)}
            >
              <option value="">Any type</option>
              <option value="pdf">PDF</option>
              <option value="text">Text</option>
              <option value="markdown">Markdown</option>
              <option value="annotation">Annotation</option>
            </select>
          </div>
          <div>
            <label className="field" htmlFor="search-document-kind">
              Document kind
            </label>
            <select
              id="search-document-kind"
              value={documentKind}
              onChange={(event) => onDocumentKindChange(event.target.value)}
            >
              <option value="">Any kind</option>
              <option value="patent_pdf">Patent PDF</option>
            </select>
          </div>
          <div>
            <label className="field" htmlFor="search-patent-section">
              Patent section
            </label>
            <select
              id="search-patent-section"
              value={patentSection}
              onChange={(event) => onPatentSectionChange(event.target.value)}
            >
              <option value="">Any patent section</option>
              {[...new Set(["claims", "abstract", "description", "examples", ...sections])].map((value) => (
                <option value={value} key={value}>
                  {value}
                </option>
              ))}
            </select>
          </div>
        </div>
        <div className="row search-toggles">
          <label className="check">
            <input
              type="checkbox"
              checked={hasTable}
              onChange={(event) => onHasTableChange(event.target.checked)}
            />
            <span>Has table hint</span>
          </label>
          <label className="check">
            <input
              type="checkbox"
              checked={hasFigure}
              onChange={(event) => onHasFigureChange(event.target.checked)}
            />
            <span>Has figure hint</span>
          </label>
        </div>
      </div>

      <div className="row row-between">
        <span className="muted">
          {message}
          {lastRebuild ? ` · ${lastRebuild.indexed_chunks} indexed chunks` : ""}
          {lastRebuild && isVectorRebuild(lastRebuild) ? ` · ${lastRebuild.model}` : ""}
        </span>
        <span className="badge">
          <span className="dot" />
          Manual rebuild
        </span>
      </div>

      {busy ? (
        <div className="card card-pad-sm">
          <div className="eyebrow">Searching</div>
          <div className="stack">
            <div className="skeleton" style={{ width: "80%" }} />
            <div className="skeleton" style={{ width: "95%" }} />
            <div className="skeleton" style={{ width: "55%" }} />
          </div>
        </div>
      ) : results.length > 0 ? (
        <div className="stack">
          {results.map((result) => (
            <SearchResultCard result={result} key={result.chunk_id} onOpen={() => onOpenResult(result)} />
          ))}
        </div>
      ) : (
        <div className="empty">
          <h3>No {searchModeLabel(mode)} results yet</h3>
          <p>Rebuild the index after document changes, then run a query.</p>
        </div>
      )}
    </>
  );
}

function SearchResultCard({
  result,
  onOpen,
}: {
  result: SearchResult;
  onOpen: () => void;
}) {
  return (
    <div className="result">
      <div className="row row-between">
        <div>
          <span className="rank">#{result.rank}</span>
          <strong> {result.document_title}</strong>
          <span className="muted">
            {" "}
            · {searchProvenanceLabel(result)} · {result.section ?? "document"} · chunk{" "}
            {result.chunk_index + 1}
          </span>
        </div>
        <button className="btn btn-sm btn-ghost" type="button" onClick={onOpen}>
          View source
        </button>
      </div>
      {result.snippet ? (
        <p
          className="search-snippet"
          dangerouslySetInnerHTML={{ __html: result.snippet }}
        />
      ) : (
        <p className="search-snippet">{result.text_preview}</p>
      )}
      <div className="scores">
        {result.score_breakdown.bm25 != null && (
          <div className="score">
            <span>BM25</span>
            <b>{Math.abs(result.score_breakdown.bm25).toFixed(4)}</b>
          </div>
        )}
        {result.score_breakdown.dense != null && (
          <div className="score">
            <span>Dense</span>
            <b>{result.score_breakdown.dense.toFixed(4)}</b>
          </div>
        )}
        {result.score_breakdown.rrf != null && (
          <div className="score">
            <span>RRF</span>
            <b>{result.score_breakdown.rrf.toFixed(4)}</b>
          </div>
        )}
        {result.score_breakdown.rerank != null && (
          <div className="score">
            <span>Rerank</span>
            <b>{result.score_breakdown.rerank.toFixed(4)}</b>
          </div>
        )}
        {result.score_breakdown.metadata_boost != null && (
          <div className="score">
            <span>Boost</span>
            <b>{result.score_breakdown.metadata_boost.toFixed(2)}</b>
          </div>
        )}
        <div className="score">
          <span>Final</span>
          <b>{result.final_score.toFixed(4)}</b>
        </div>
        <div className="score">
          <span>Rank</span>
          <b>{result.rank}</b>
        </div>
        {result.matched_fields.length > 0 ? (
          <div className="score">
            <span>Fields</span>
            <b>{result.matched_fields.join(", ")}</b>
          </div>
        ) : result.embedding_model ? (
          <div className="score">
            <span>Embedding</span>
            <b>{shortModelName(result.embedding_model)}</b>
          </div>
        ) : null}
      </div>
      {(result.source_ranks.full_text || result.source_ranks.vector) && (
        <p className="hint">
          full-text rank {result.source_ranks.full_text ?? "—"} · vector rank{" "}
          {result.source_ranks.vector ?? "—"}
        </p>
      )}
      {result.embedding_model && result.embedding_run_id && (
        <p className="hint">
          {result.embedding_provider} · {result.vector_size}d · {result.collection_name} · run{" "}
          {result.embedding_run_id.slice(0, 8)}
        </p>
      )}
      <div className="row result-meta">
        {result.metadata.source_type && <span className="badge">{result.metadata.source_type}</span>}
        {result.metadata.document_kind && <span className="badge">{result.metadata.document_kind}</span>}
        {result.metadata.has_table && <span className="badge">table</span>}
        {result.metadata.has_figure && <span className="badge">figure</span>}
        {result.metadata.patent_sections?.map((section) => (
          <span className="badge" key={section}>
            {section}
          </span>
        ))}
      </div>
      <p className="hint citation">
        Citation: [{result.document_title}, {searchProvenanceLabel(result)}, chunk{" "}
        {result.chunk_index + 1}]
      </p>
    </div>
  );
}

function PageImageStrip({ images, pageCount }: { images: PageImage[]; pageCount: number }) {
  if (images.length === 0) {
    return (
      <div className="page-image-empty">
        {pageCount > 0 ? "No page thumbnails are available for this PDF." : "No PDF pages detected."}
      </div>
    );
  }
  return (
    <div className="page-image-strip">
      {images.map((image) => (
        <a
          className="page-thumb"
          href={absoluteApiUrl(image.url)}
          key={image.page}
          title={`Open page ${image.page}`}
        >
          <img src={absoluteApiUrl(image.url)} alt={`Page ${image.page}`} />
          <span>p. {image.page}</span>
        </a>
      ))}
    </div>
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
  const structureHints = version.metadata.structure_hints;
  if (Array.isArray(structureHints) && structureHints.length > 0) {
    return `Source structure hints: ${structureHints.join(", ")}`;
  }
  if (version.ocr_required) {
    return "This document has little extractable text and should be inspected with OCR/page images.";
  }
  if (version.warnings.length > 0) {
    return version.warnings.join(" ");
  }
  return `${version.parser_version} produced inspectable source chunks.`;
}

function absoluteApiUrl(path: string) {
  if (path.startsWith("http")) {
    return path;
  }
  return `${API_BASE}${path}`;
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

function offsetLabel(chunk: Chunk) {
  if (chunk.char_start !== null && chunk.char_end !== null) {
    return `${chunk.char_start}-${chunk.char_end}`;
  }
  return "—";
}

function chunkContextWindow(chunks: Chunk[], selectedChunkId: string, radius = 1) {
  const selectedIndex = chunks.findIndex((chunk) => chunk.id === selectedChunkId);
  if (selectedIndex < 0) {
    return chunks.slice(0, radius * 2 + 1);
  }
  const start = Math.max(0, selectedIndex - radius);
  const end = Math.min(chunks.length, selectedIndex + radius + 1);
  return chunks.slice(start, end);
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

function searchProvenanceLabel(result: SearchResult) {
  if (result.page_start) {
    return `p. ${result.page_start}${result.page_end && result.page_end !== result.page_start ? `-${result.page_end}` : ""}`;
  }
  if (result.line_start) {
    return `lines ${result.line_start}${result.line_end && result.line_end !== result.line_start ? `-${result.line_end}` : ""}`;
  }
  return result.section ?? "document";
}

function citationProvenanceLabel(citation: ChatCitation) {
  if (citation.page_start) {
    return `p. ${citation.page_start}${citation.page_end && citation.page_end !== citation.page_start ? `-${citation.page_end}` : ""}`;
  }
  if (citation.line_start) {
    return `lines ${citation.line_start}${citation.line_end && citation.line_end !== citation.line_start ? `-${citation.line_end}` : ""}`;
  }
  return citation.section ?? "document";
}

function searchModeLabel(mode: SearchMode) {
  return mode === "vector" ? "vector" : mode === "hybrid" ? "hybrid" : "full-text";
}

function apiSearchMode(mode: SearchMode) {
  return mode === "full-text" ? "full_text" : mode;
}

function isVectorRebuild(rebuild: SearchRebuildResponse): rebuild is VectorRebuildResponse {
  return "embedding_run_id" in rebuild;
}

function shortModelName(model: string) {
  const parts = model.split("/");
  return parts[parts.length - 1] ?? model;
}

function viewFromHash(hash: string): View {
  if (hash === "#chat-workspace") {
    return "chat";
  }
  if (hash === "#search-lab") {
    return "search";
  }
  if (hash === "#source-viewer") {
    return "source";
  }
  return "documents";
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);
