import React, { useEffect, useMemo, useRef, useState } from "react";
import ReactDOM from "react-dom/client";
import "./styles.css";

const API_BASE = "http://127.0.0.1:8000";

type RepositoryResponse = {
  repository: RepositoryRead;
};

type RepositoryRead = {
  id: string;
  name: string;
  root_path?: string | null;
  created_at?: string;
  updated_at?: string;
};

type RepositorySettings = {
  chunking: {
    chunk_size: number;
    chunk_overlap: number;
    mode: string;
  };
  parser: {
    structured_parser: string;
    fallback_parser: string;
  };
  full_text: {
    tokenizer: string;
    prefix_index: boolean;
    porter_stemming: boolean;
  };
  vector: {
    collection_name: string;
    vector_size: number;
    distance: string;
  };
  embedding: {
    provider: string;
    model: string;
  };
  reranking: {
    strategy: string;
    model: string | null;
  };
  model: {
    ollama_chat_model: string;
  };
  prompt: {
    version: string;
    active_chat_prompt_id: string;
    library: Array<{
      id: string;
      name: string;
      text: string;
    }>;
  };
  export: {
    include_sources: boolean;
    include_indexes: boolean;
    format: string;
  };
};

type RepositorySettingsResponse = RepositoryResponse & {
  settings: RepositorySettings;
};

type ExportManifestSummary = {
  generated_at: string;
  repository: {
    id: string;
    name: string;
  };
  export_options: {
    include_sources: boolean;
    include_sandbox: boolean;
    format: string;
  };
  counts: Record<string, number>;
  required_models: string[];
  settings_summary: string[];
  warnings: string[];
};

type ExportBundleSource = {
  document_id: string;
  document_version_id: string;
  original_filename: string;
  content_type: string | null;
  source_type: string;
  sha256: string;
  byte_size: number;
  original_storage_path: string;
  bundle_path: string | null;
  included: boolean;
  missing: boolean;
};

type ExportBundleManifest = {
  bundle_schema_version: 1;
  bundle_format: string;
  generated_at: string;
  repository: Record<string, unknown>;
  export_options: Record<string, unknown>;
  settings: Record<string, unknown>;
  required_models: string[];
  payloads: Record<string, string>;
  sources: ExportBundleSource[];
  counts: Record<string, number>;
  warnings: string[];
};

type ExportBundleValidationIssue = {
  severity: "error" | "warning" | "info";
  code: string;
  message: string;
  path: string | null;
  setting: string | null;
  source_sha256: string | null;
  document_version_id: string | null;
};

type ExportBundleValidationResponse = {
  can_recreate: boolean;
  manifest: ExportBundleManifest | null;
  counts: Record<string, number>;
  required_models: string[];
  blocking_errors: ExportBundleValidationIssue[];
  warnings: ExportBundleValidationIssue[];
  informational: ExportBundleValidationIssue[];
};

type RecreateSourceMapping = {
  sha256: string;
  path: string;
  document_version_id?: string;
};

type RecreateSourceResult = {
  original_document_id: string;
  original_document_version_id: string;
  recreated_document_id: string | null;
  recreated_document_version_id: string | null;
  original_filename: string;
  source_sha256: string;
  source_path: string | null;
  expected_chunk_count: number;
  actual_chunk_count: number;
  status: string;
};

type RecreateIndexReport = {
  full_text_indexed_chunks: number;
  vector_indexed_chunks: number;
  vector_collection_name: string | null;
  vector_distance: string | null;
  vector_size: number | null;
  vector_model: string | null;
};

type RecreateBundleResponse = {
  status: "completed" | "failed";
  repository_id: string | null;
  repository_name: string | null;
  validation: ExportBundleValidationResponse;
  restored_counts: Record<string, number>;
  sources: RecreateSourceResult[];
  indexes: RecreateIndexReport;
  warnings: ExportBundleValidationIssue[];
};

type View = "documents" | "source" | "search" | "sandbox" | "chat" | "export" | "recreate";

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
  text_preview: string | null;
};

type ChatRetrievalSettings = {
  mode: "full_text" | "vector" | "hybrid";
  top_k: number;
  reranker_strategy: RerankerStrategy;
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
  retrieval_settings: ChatRetrievalSettings;
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

type ChatReadinessItem = {
  ready: boolean;
  status: "ready" | "missing" | "partial" | "stale";
  message: string;
  indexed_chunks: number | null;
  model: string | null;
};

type ChatReadiness = {
  repository_id: string;
  parsed_chunks: number;
  full_text: ChatReadinessItem;
  vector: ChatReadinessItem;
  local_model: ChatReadinessItem;
  ready_for_chat: boolean;
};

type SandboxPromptVersion = {
  id: string;
  repository_id: string;
  name: string;
  body: string;
  notes: string | null;
  source_chat_prompt_id: string | null;
  used_by_run: boolean;
  created_at: string;
};

type SandboxRun = {
  id: string;
  repository_id: string;
  prompt_version_id: string | null;
  comparison_id: string | null;
  comparison_index: number | null;
  label: string | null;
  query: string;
  model: string;
  retrieval_settings: ChatRetrievalSettings;
  prompt_snapshot: Record<string, unknown>;
  context_entries: RetrievalSearchResult[];
  retrieval_run_id: string | null;
  answer: string;
  citations: ChatCitation[];
  metrics: Record<string, unknown>;
  latency_ms: number;
  status: string;
  created_at: string;
};

type SandboxComparison = {
  id: string;
  repository_id: string;
  query: string;
  status: string;
  expected_run_count: number;
  runs: SandboxRun[];
  created_at: string;
};

type SandboxComparisonRunConfig = ReturnType<typeof sandboxComparisonRunConfigs>[number];

type SandboxProgressRun = {
  id: string;
  label: string;
  model: string;
  retrieval_settings: ChatRetrievalSettings;
  status: "pending" | "running" | "completed" | "failed";
  run: SandboxRun | null;
  error: string | null;
};

function App() {
  const [repository, setRepository] = useState<RepositoryResponse["repository"] | null>(null);
  const [repositories, setRepositories] = useState<RepositoryRead[]>([]);
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
  const [chatRetrievalSettings, setChatRetrievalSettings] = useState<ChatRetrievalSettings>({
    mode: "hybrid",
    top_k: 6,
    reranker_strategy: "cross_encoder",
  });
  const [chatReadiness, setChatReadiness] = useState<ChatReadiness | null>(null);
  const [chatReadinessBusy, setChatReadinessBusy] = useState(false);
  const [chatReadinessCheckedAt, setChatReadinessCheckedAt] = useState<string | null>(null);
  const [chatRebuildBusy, setChatRebuildBusy] = useState<"full-text" | "vector" | null>(null);
  const [sandboxPrompts, setSandboxPrompts] = useState<SandboxPromptVersion[]>([]);
  const [sandboxPromptName, setSandboxPromptName] = useState("Scientific grounded prompt");
  const [sandboxPromptBody, setSandboxPromptBody] = useState(
    "Answer only from retrieved repository context. Cite every factual claim with inline citation tokens such as [1]. If the retrieved context is insufficient, say so.",
  );
  const [selectedSandboxPromptId, setSelectedSandboxPromptId] = useState<string | null>(null);
  const [sandboxQuery, setSandboxQuery] = useState("LiFePO4 cathodes retain capacity cycling");
  const [sandboxModel, setSandboxModel] = useState("gemma3:4b");
  const [sandboxTopK, setSandboxTopK] = useState(3);
  const [sandboxComparison, setSandboxComparison] = useState<SandboxComparison | null>(null);
  const [sandboxProgressRuns, setSandboxProgressRuns] = useState<SandboxProgressRun[]>([]);
  const [sandboxBusy, setSandboxBusy] = useState(false);
  const [sandboxMessage, setSandboxMessage] = useState("Save a prompt, then run a comparison.");
  const [repositorySettings, setRepositorySettings] = useState<RepositorySettings | null>(null);
  const [exportIncludeSources, setExportIncludeSources] = useState(true);
  const [exportIncludeSandbox, setExportIncludeSandbox] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportMessage, setExportMessage] = useState("Ready to export");
  const [exportDownloadUrl, setExportDownloadUrl] = useState<string | null>(null);
  const [exportFilename, setExportFilename] = useState<string | null>(null);
  const [exportSummary, setExportSummary] = useState<ExportManifestSummary | null>(null);
  const [recreateFile, setRecreateFile] = useState<File | null>(null);
  const [recreateRepositoryName, setRecreateRepositoryName] = useState("");
  const [recreateTargetRepositoryId, setRecreateTargetRepositoryId] = useState("");
  const [recreateAvailableModels, setRecreateAvailableModels] = useState("");
  const [recreateSourceMappings, setRecreateSourceMappings] = useState<RecreateSourceMapping[]>([]);
  const [recreateValidation, setRecreateValidation] = useState<ExportBundleValidationResponse | null>(null);
  const [recreateResult, setRecreateResult] = useState<RecreateBundleResponse | null>(null);
  const [recreateBusy, setRecreateBusy] = useState<"validating" | "recreating" | null>(null);
  const [recreateMessage, setRecreateMessage] = useState("Select an export ZIP bundle");
  const [pendingSourceTarget, setPendingSourceTarget] = useState<{
    documentId: string;
    chunkId: string;
  } | null>(null);

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
      void loadRepositorySettings(repository.id);
      void loadChatSessions(repository.id);
      void loadChatReadiness(repository.id);
      void loadSandboxPrompts(repository.id);
    }
  }, [repository]);

  useEffect(() => {
    return () => {
      if (exportDownloadUrl) {
        URL.revokeObjectURL(exportDownloadUrl);
      }
    };
  }, [exportDownloadUrl]);

  useEffect(() => {
    if (repository && selectedDocumentId) {
      void inspectDocument(repository.id, selectedDocumentId);
    }
  }, [repository, selectedDocumentId]);

  useEffect(() => {
    if (
      pendingSourceTarget &&
      inspection?.document.id === pendingSourceTarget.documentId &&
      inspection.chunks.some((chunk) => chunk.id === pendingSourceTarget.chunkId)
    ) {
      setSelectedChunkId(pendingSourceTarget.chunkId);
      setPendingSourceTarget(null);
      return;
    }
    setSelectedChunkId((current) =>
      current && inspection?.chunks.some((chunk) => chunk.id === current)
        ? current
        : (inspection?.chunks[0]?.id ?? null),
    );
  }, [inspection, pendingSourceTarget]);

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

  useEffect(() => {
    if (activeChatSession) {
      setChatRetrievalSettings(normalizeChatRetrievalSettings(activeChatSession.retrieval_settings));
    }
  }, [activeChatSession?.id]);

  useEffect(() => {
    if (repository && activeChatSessionId) {
      void loadChatSession(repository.id, activeChatSessionId);
    }
  }, [repository?.id, activeChatSessionId]);

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
      const response = await fetch(`${API_BASE}/repositories`);
      if (!response.ok) {
        throw new Error("repositories unavailable");
      }
      const payload = (await response.json()) as RepositoryRead[];
      setRepositories(payload);
      const storedRepositoryId = window.localStorage.getItem("activeRepositoryId");
      const selectedRepository =
        (storedRepositoryId ? payload.find((item) => item.id === storedRepositoryId) : null) ??
        payload.find((item) => item.name === "Default Repository") ??
        payload[0] ??
        null;
      if (selectedRepository) {
        activateRepository(selectedRepository);
      }
      setMessage("Ready");
    } catch {
      try {
        const response = await fetch(`${API_BASE}/repositories/default`);
        const payload = (await response.json()) as RepositoryResponse;
        activateRepository(payload.repository);
        setRepositories([payload.repository]);
        setMessage("Ready");
      } catch {
        setMessage("Backend unavailable");
      }
    }
  }

  function activateRepository(nextRepository: RepositoryRead) {
    window.localStorage.setItem("activeRepositoryId", nextRepository.id);
    setRepository(nextRepository);
    setDocuments([]);
    setSelectedDocumentId(null);
    setSelectedChunkId(null);
    setInspection(null);
    setSearchDocumentId("");
    setSearchResults([]);
    setLastRebuild(null);
    setChatSessions([]);
    setActiveChatSessionId(null);
    setActiveCitation(null);
    setChatMessage("Loading chat sessions");
    setChatReadiness(null);
    setChatReadinessCheckedAt(null);
    setSandboxPrompts([]);
    setSelectedSandboxPromptId(null);
    setSandboxComparison(null);
    setSandboxProgressRuns([]);
    setSandboxMessage("Loading sandbox prompts");
  }

  async function loadDocuments(repositoryId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/documents`);
      const payload = (await response.json()) as DocumentSummary[];
      setDocuments(payload);
      setSelectedDocumentId((current) =>
        current && payload.some((document) => document.id === current)
          ? current
          : (payload[0]?.id ?? null),
      );
    } catch {
      setMessage("Could not load documents");
    }
  }

  async function loadRepositorySettings(repositoryId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/settings`);
      if (!response.ok) {
        throw new Error("settings unavailable");
      }
      const payload = (await response.json()) as RepositorySettingsResponse;
      setRepositorySettings(payload.settings);
      setExportIncludeSources(payload.settings.export.include_sources);
    } catch {
      setRepositorySettings(null);
      setExportMessage("Could not load export defaults");
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
      setActiveChatSessionId((current) =>
        current && payload.some((session) => session.id === current)
          ? current
          : (payload[0]?.id ?? null),
      );
      setChatMessage(payload.length > 0 ? "Ready" : "No chat sessions yet");
    } catch {
      setChatMessage("Could not load chat sessions");
    }
  }

  async function loadChatSession(repositoryId: string, chatSessionId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/chat/sessions/${chatSessionId}`);
      if (!response.ok) {
        throw new Error("chat session unavailable");
      }
      const payload = (await response.json()) as ChatSession;
      setChatSessions((current) =>
        current.map((session) => (session.id === payload.id ? payload : session)),
      );
      setChatMessage("Ready");
    } catch {
      setChatMessage("Could not load chat history");
    }
  }

  async function loadChatReadiness(repositoryId: string, announce = false) {
    if (announce) {
      setChatReadinessBusy(true);
      setChatMessage("Checking chat readiness");
    }
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/chat/readiness`);
      if (!response.ok) {
        throw new Error("readiness unavailable");
      }
      setChatReadiness((await response.json()) as ChatReadiness);
      setChatReadinessCheckedAt(new Date().toISOString());
      if (announce) {
        setChatMessage("Readiness check complete");
      }
    } catch {
      setChatReadiness(null);
      if (announce) {
        setChatMessage("Could not check chat readiness");
      }
    } finally {
      if (announce) {
        setChatReadinessBusy(false);
      }
    }
  }

  async function loadSandboxPrompts(repositoryId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/prompt-sandbox/prompts`);
      if (!response.ok) {
        throw new Error("sandbox prompts unavailable");
      }
      const payload = (await response.json()) as SandboxPromptVersion[];
      setSandboxPrompts(payload);
      const selectedPromptStillExists = payload.some((prompt) => prompt.id === selectedSandboxPromptId);
      if (!selectedPromptStillExists && payload.length > 0) {
        const latest = payload[payload.length - 1];
        setSelectedSandboxPromptId(latest.id);
        setSandboxPromptName(latest.name);
        setSandboxPromptBody(latest.body);
      } else if (!selectedPromptStillExists) {
        setSelectedSandboxPromptId(null);
      }
    } catch {
      setSandboxMessage("Could not load sandbox prompts");
    }
  }

  async function saveSandboxPrompt(manageBusy = true) {
    if (!repository || !sandboxPromptName.trim() || !sandboxPromptBody.trim()) {
      return null;
    }
    if (manageBusy) {
      setSandboxBusy(true);
    }
    setSandboxMessage("Saving prompt version");
    try {
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/prompt-sandbox/prompts`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: sandboxPromptName.trim(),
          body: sandboxPromptBody.trim(),
        }),
      });
      if (!response.ok) {
        throw new Error("save sandbox prompt failed");
      }
      const prompt = (await response.json()) as SandboxPromptVersion;
      setSandboxPrompts((current) => [...current, prompt]);
      setSelectedSandboxPromptId(prompt.id);
      setSandboxMessage("Prompt version saved");
      return prompt;
    } catch {
      setSandboxMessage("Could not save prompt version");
      return null;
    } finally {
      if (manageBusy) {
        setSandboxBusy(false);
      }
    }
  }

  async function deleteSandboxPrompt() {
    if (!repository || !selectedSandboxPromptId) {
      return;
    }
    setSandboxBusy(true);
    setSandboxMessage("Deleting prompt version");
    try {
      const deletedPromptId = selectedSandboxPromptId;
      const response = await fetch(
        `${API_BASE}/repositories/${repository.id}/prompt-sandbox/prompts/${deletedPromptId}`,
        {
          method: "DELETE",
        },
      );
      if (!response.ok) {
        throw new Error("delete sandbox prompt failed");
      }
      setSandboxPrompts((current) => {
        const remaining = current.filter((prompt) => prompt.id !== deletedPromptId);
        const nextPrompt = remaining[remaining.length - 1] ?? null;
        setSelectedSandboxPromptId(nextPrompt?.id ?? null);
        if (nextPrompt) {
          setSandboxPromptName(nextPrompt.name);
          setSandboxPromptBody(nextPrompt.body);
        }
        return remaining;
      });
      setSandboxMessage("Prompt version deleted");
    } catch {
      setSandboxMessage("Could not delete prompt version");
    } finally {
      setSandboxBusy(false);
    }
  }

  async function runSandboxComparison() {
    if (!repository || !sandboxQuery.trim()) {
      return;
    }
    setSandboxBusy(true);
    setSandboxMessage("Running comparison");
    try {
      const selectedPrompt =
        sandboxPrompts.find((prompt) => prompt.id === selectedSandboxPromptId) ??
        (await saveSandboxPrompt(false));
      if (!selectedPrompt) {
        throw new Error("missing sandbox prompt");
      }
      const runConfigs = sandboxComparisonRunConfigs(selectedPrompt.id, sandboxModel, sandboxTopK);
      setSandboxProgressRuns(progressRunsFromConfigs(runConfigs, "pending"));
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/prompt-sandbox/comparisons`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          query: sandboxQuery.trim(),
          runs: runConfigs,
          execute_immediately: false,
        }),
      });
      if (!response.ok) {
        throw new Error("sandbox comparison failed");
      }
      const comparison = (await response.json()) as SandboxComparison;
      setSandboxComparison(comparison);
      setSandboxMessage(`Running comparison · 0/${runConfigs.length} complete`);
      const completedRuns = await Promise.all(
        runConfigs.map((runConfig, index) =>
          runSandboxComparisonRun(repository.id, comparison.id, runConfig, index),
        ),
      );
      const successfulRuns = completedRuns.filter((run): run is SandboxRun => run !== null);
      const failedCount = completedRuns.length - successfulRuns.length;
      const reloadResponse = await fetch(
        `${API_BASE}/repositories/${repository.id}/prompt-sandbox/comparisons/${comparison.id}`,
      );
      if (reloadResponse.ok) {
        setSandboxComparison((await reloadResponse.json()) as SandboxComparison);
      } else {
        setSandboxComparison({
          ...comparison,
          status: failedCount > 0 ? "failed" : "completed",
          runs: successfulRuns,
        });
      }
      setSandboxMessage(
        failedCount > 0
          ? `Comparison finished with ${failedCount} failed run${failedCount === 1 ? "" : "s"}`
          : `Comparison complete · ${successfulRuns.length} runs`,
      );
    } catch {
      setSandboxProgressRuns((current) =>
        current.map((run) =>
          run.status === "completed"
            ? run
            : {
                ...run,
                status: "failed",
                error: "Could not run this retrieval mode.",
              },
        ),
      );
      setSandboxMessage("Could not run comparison");
    } finally {
      setSandboxBusy(false);
    }
  }

  async function runSandboxComparisonRun(
    repositoryId: string,
    comparisonId: string,
    runConfig: SandboxComparisonRunConfig,
    index: number,
  ) {
    setSandboxProgressRuns((current) =>
      current.map((run) => (run.id === runConfig.label ? { ...run, status: "running" } : run)),
    );
    try {
      const response = await fetch(
        `${API_BASE}/repositories/${repositoryId}/prompt-sandbox/comparisons/${comparisonId}/runs`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            ...runConfig,
            comparison_index: index,
          }),
        },
      );
      if (!response.ok) {
        throw new Error("sandbox comparison run failed");
      }
      const run = (await response.json()) as SandboxRun;
      setSandboxProgressRuns((current) => {
        const next = current.map((progressRun) =>
          progressRun.id === runConfig.label
            ? {
                ...progressRun,
                status: "completed" as const,
                run,
                error: null,
              }
            : progressRun,
        );
        const completeCount = next.filter((progressRun) => progressRun.status === "completed").length;
        setSandboxMessage(`Running comparison · ${completeCount}/${next.length} complete`);
        return next;
      });
      return run;
    } catch {
      setSandboxProgressRuns((current) =>
        current.map((progressRun) =>
          progressRun.id === runConfig.label
            ? {
                ...progressRun,
                status: "failed",
                error: "Could not complete this retrieval mode.",
              }
            : progressRun,
        ),
      );
      return null;
    }
  }

  async function createChatSession(manageBusy = true) {
    if (!repository) {
      return null;
    }
    if (manageBusy) {
      setChatBusy(true);
    }
    setChatMessage("Creating chat session");
    try {
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/chat/sessions`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          title: "Repository chat",
          retrieval_settings: chatRetrievalSettings,
        }),
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
      if (manageBusy) {
        setChatBusy(false);
      }
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
      const chatSession = activeChatSession ?? (await createChatSession(false));
      if (!chatSession) {
        throw new Error("missing chat session");
      }
      const response = await fetch(
        `${API_BASE}/repositories/${repository.id}/chat/sessions/${chatSession.id}/messages`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ content, retrieval_settings: chatRetrievalSettings }),
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
      setChatRetrievalSettings(payload.session.retrieval_settings);
      void loadChatReadiness(repository.id);
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

  async function deleteChatSession(chatSessionId: string) {
    if (!repository) {
      return;
    }
    setChatMessage("Deleting chat session");
    try {
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/chat/sessions/${chatSessionId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("delete failed");
      }
      setChatSessions((current) => current.filter((session) => session.id !== chatSessionId));
      setActiveChatSessionId((current) =>
        current === chatSessionId ? chatSessions.find((session) => session.id !== chatSessionId)?.id ?? null : current,
      );
      setChatMessage("Chat session deleted");
    } catch {
      setChatMessage("Could not delete chat session");
    }
  }

  async function clearChatSessions() {
    if (!repository || chatSessions.length === 0) {
      return;
    }
    const confirmed = window.confirm("Clear all chat sessions for this repository?");
    if (!confirmed) {
      return;
    }
    setChatMessage("Clearing chat sessions");
    try {
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/chat/sessions`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("clear failed");
      }
      setChatSessions([]);
      setActiveChatSessionId(null);
      setActiveCitation(null);
      setChatMessage("All chat sessions cleared");
    } catch {
      setChatMessage("Could not clear chat sessions");
    }
  }

  async function rebuildChatIndex(kind: "full-text" | "vector") {
    if (!repository) {
      return;
    }
    setChatRebuildBusy(kind);
    setChatMessage(`Rebuilding ${kind} index`);
    try {
      const endpoint = kind === "vector" ? "vector" : "full-text";
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/${endpoint}/rebuild`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("rebuild failed");
      }
      const payload = (await response.json()) as SearchRebuildResponse;
      setChatMessage(`Indexed ${payload.indexed_chunks} ${kind} chunks`);
      await loadChatReadiness(repository.id);
    } catch {
      setChatMessage(`${kind} rebuild failed`);
    } finally {
      setChatRebuildBusy(null);
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
    await deleteDocument(selectedDocumentId);
  }

  async function deleteDocument(documentId: string) {
    if (!repository) {
      return;
    }
    const document = documents.find((item) => item.id === documentId);
    const confirmed = window.confirm(`Delete ${document?.display_name ?? "this document"}?`);
    if (!confirmed) {
      return;
    }
    setBusy(true);
    setMessage("Deleting document");
    try {
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/documents/${documentId}`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("delete failed");
      }
      if (selectedDocumentId === documentId) {
        setSelectedDocumentId(null);
        setInspection(null);
      }
      await loadDocuments(repository.id);
      await loadChatReadiness(repository.id);
      setMessage("Deleted");
    } catch {
      setMessage("Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function deleteAllDocuments() {
    if (!repository || documents.length === 0) {
      return;
    }
    const confirmed = window.confirm("Delete all documents in this repository?");
    if (!confirmed) {
      return;
    }
    setBusy(true);
    setMessage("Deleting all documents");
    try {
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/documents`, {
        method: "DELETE",
      });
      if (!response.ok) {
        throw new Error("delete all failed");
      }
      setSelectedDocumentId(null);
      setInspection(null);
      setSelectedChunkId(null);
      await loadDocuments(repository.id);
      await loadChatReadiness(repository.id);
      setMessage("All documents deleted");
    } catch {
      setMessage("Delete all failed");
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

  async function exportRepositoryBundle() {
    if (!repository) {
      return;
    }
    setExportBusy(true);
    setExportMessage("Preparing export bundle");
    setExportSummary(null);
    try {
      const params = new URLSearchParams({
        include_sources: String(exportIncludeSources),
        include_sandbox: String(exportIncludeSandbox),
      });
      const response = await fetch(`${API_BASE}/repositories/${repository.id}/exports/bundle?${params}`, {
        method: "POST",
      });
      if (!response.ok) {
        throw new Error("export failed");
      }
      const blob = await response.blob();
      if (exportDownloadUrl) {
        URL.revokeObjectURL(exportDownloadUrl);
      }
      const downloadUrl = URL.createObjectURL(blob);
      const filename =
        filenameFromContentDisposition(response.headers.get("Content-Disposition")) ??
        `${repository.name.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-|-$/g, "") || "repository"}-export.zip`;

      setExportDownloadUrl(downloadUrl);
      setExportFilename(filename);
      setExportSummary(
        buildExportManifestSummary({
          repository,
          documents,
          totalChunks,
          chatSessions,
          sandboxPrompts,
          settings: repositorySettings,
          includeSources: exportIncludeSources,
          includeSandbox: exportIncludeSandbox,
        }),
      );
      setExportMessage(`Export ready · ${formatBytes(blob.size)}`);
    } catch {
      setExportDownloadUrl(null);
      setExportFilename(null);
      setExportSummary(null);
      setExportMessage("Export failed");
    } finally {
      setExportBusy(false);
    }
  }

  async function validateRecreateBundle() {
    if (!recreateFile) {
      return;
    }
    setRecreateBusy("validating");
    setRecreateResult(null);
    setRecreateMessage("Validating bundle");
    try {
      const response = await fetch(`${API_BASE}/repositories/recreate/bundle/validate`, {
        method: "POST",
        body: recreateFormData(recreateFile, {
          availableModelsText: recreateAvailableModels,
          sourceMappings: recreateSourceMappings,
        }),
      });
      if (!response.ok) {
        throw new Error("bundle validation failed");
      }
      const payload = (await response.json()) as ExportBundleValidationResponse;
      setRecreateValidation(payload);
      setRecreateSourceMappings((current) => mergeSourceMappings(current, payload));
      setRecreateMessage(payload.can_recreate ? "Bundle can be recreated" : "Bundle has blocking issues");
    } catch {
      setRecreateValidation(null);
      setRecreateMessage("Validation failed");
    } finally {
      setRecreateBusy(null);
    }
  }

  async function runRecreateBundle() {
    if (!recreateFile || !recreateValidation?.can_recreate) {
      return;
    }
    setRecreateBusy("recreating");
    setRecreateResult(null);
    setRecreateMessage("Recreating repository");
    try {
      const response = await fetch(`${API_BASE}/repositories/recreate/bundle`, {
        method: "POST",
        body: recreateFormData(recreateFile, {
          repositoryName: recreateRepositoryName,
          targetRepositoryId: recreateTargetRepositoryId,
          availableModelsText: recreateAvailableModels,
          sourceMappings: recreateSourceMappings,
        }),
      });
      if (!response.ok) {
        throw new Error("recreate failed");
      }
      const payload = (await response.json()) as RecreateBundleResponse;
      setRecreateResult(payload);
      setRecreateValidation(payload.validation);
      if (payload.status === "completed" && payload.repository_id) {
        const recreatedRepository = {
          id: payload.repository_id,
          name: payload.repository_name ?? "Recreated repository",
        };
        setRepositories((current) => mergeRepositories(current, recreatedRepository));
        activateRepository(recreatedRepository);
      }
      setRecreateMessage(payload.status === "completed" ? "Recreate complete" : "Recreate failed");
    } catch {
      setRecreateResult(null);
      setRecreateMessage("Recreate failed");
    } finally {
      setRecreateBusy(null);
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
            : view === "sandbox"
              ? "prompt-sandbox"
              : view === "export"
                ? "export-center"
                : view === "recreate"
                  ? "recreate-repository"
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
    setPendingSourceTarget({ documentId: citation.document_id, chunkId: citation.chunk_id });
    setSelectedDocumentId(citation.document_id);
    setActiveCitation(null);
    navigateTo("source");
  }

  function openSandboxContext(result: RetrievalSearchResult) {
    setSelectedDocumentId(result.document_id);
    setSelectedChunkId(result.chunk_id);
    navigateTo("source");
  }

  const title =
    activeView === "search"
      ? "Search Lab"
      : activeView === "source"
        ? "Source Viewer"
        : activeView === "chat"
          ? "Chat Workspace"
          : activeView === "sandbox"
            ? "Prompt Sandbox"
            : activeView === "export"
              ? "Export Center"
              : activeView === "recreate"
                ? "Recreate Repository"
          : "Document Manager";
  const subtitle =
    activeView === "search"
      ? "Inspect full-text retrieval with BM25 scores and citation provenance"
      : activeView === "sandbox"
        ? `${repository?.name ?? "Default Repository"} · ${sandboxMessage}`
      : activeView === "export"
        ? `${repository?.name ?? "Default Repository"} · ${exportMessage}`
      : activeView === "recreate"
        ? `${repository?.name ?? "Default Repository"} · ${recreateMessage}`
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
            <a
              className={activeView === "sandbox" ? "active" : ""}
              href="#prompt-sandbox"
              onClick={() => navigateTo("sandbox")}
            >
              Prompt Sandbox
            </a>
            <a
              className={activeView === "chat" ? "active" : ""}
              href="#chat-workspace"
              onClick={() => navigateTo("chat")}
            >
              Chat Workspace
            </a>
            <span className="nav-label">Manage</span>
            <a>Settings / Models</a>
            <a
              className={activeView === "recreate" ? "active" : ""}
              href="#recreate-repository"
              onClick={() => navigateTo("recreate")}
            >
              Recreate Repository
            </a>
            <a
              className={activeView === "export" ? "active" : ""}
              href="#export-center"
              onClick={() => navigateTo("export")}
            >
              Export Center
            </a>
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
              <label className="repository-picker" htmlFor="active-repository">
                <span>Repository</span>
                <select
                  id="active-repository"
                  value={repository?.id ?? ""}
                  onChange={(event) => {
                    const selectedRepository = repositories.find((item) => item.id === event.target.value);
                    if (selectedRepository) {
                      activateRepository(selectedRepository);
                    }
                  }}
                  disabled={repositories.length === 0}
                >
                  {repositories.map((item) => (
                    <option value={item.id} key={item.id}>
                      {item.name}
                    </option>
                  ))}
                </select>
              </label>
              {activeView === "documents" && (
                <>
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
                    className="btn btn-ghost danger-action"
                    type="button"
                    onClick={() => void deleteAllDocuments()}
                    disabled={busy || documents.length === 0}
                  >
                    Delete all
                  </button>
                </>
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
                retrievalSettings={chatRetrievalSettings}
                readiness={chatReadiness}
                readinessBusy={chatReadinessBusy}
                readinessCheckedAt={chatReadinessCheckedAt}
                rebuildBusy={chatRebuildBusy}
                onInputChange={setChatInput}
                onCreateSession={() => void createChatSession()}
                onSelectSession={setActiveChatSessionId}
                onDeleteSession={(chatSessionId) => void deleteChatSession(chatSessionId)}
                onClearSessions={() => void clearChatSessions()}
                onAsk={() => void askChatQuestion()}
                onRetrievalSettingsChange={setChatRetrievalSettings}
                onRebuildFullText={() => void rebuildChatIndex("full-text")}
                onRebuildVector={() => void rebuildChatIndex("vector")}
                onCheckReadiness={() => repository && void loadChatReadiness(repository.id, true)}
                onCitationClick={setActiveCitation}
                onCloseCitation={() => setActiveCitation(null)}
                onOpenCitation={openChatCitation}
              />
            ) : activeView === "sandbox" ? (
              <PromptSandbox
                prompts={sandboxPrompts}
                selectedPromptId={selectedSandboxPromptId}
                promptName={sandboxPromptName}
                promptBody={sandboxPromptBody}
                query={sandboxQuery}
                model={sandboxModel}
                topK={sandboxTopK}
                comparison={sandboxComparison}
                progressRuns={sandboxProgressRuns}
                busy={sandboxBusy}
                message={sandboxMessage}
                onSelectPrompt={(promptId) => {
                  setSelectedSandboxPromptId(promptId);
                  const prompt = sandboxPrompts.find((item) => item.id === promptId);
                  if (prompt) {
                    setSandboxPromptName(prompt.name);
                    setSandboxPromptBody(prompt.body);
                  }
                }}
                onPromptNameChange={setSandboxPromptName}
                onPromptBodyChange={setSandboxPromptBody}
                onQueryChange={setSandboxQuery}
                onModelChange={setSandboxModel}
                onTopKChange={setSandboxTopK}
                onSavePrompt={() => void saveSandboxPrompt()}
                onDeletePrompt={() => void deleteSandboxPrompt()}
                onRunComparison={() => void runSandboxComparison()}
                onOpenContext={openSandboxContext}
              />
            ) : activeView === "export" ? (
              <ExportCenter
                repository={repository}
                documents={documents}
                totalChunks={totalChunks}
                chatSessions={chatSessions}
                sandboxPrompts={sandboxPrompts}
                settings={repositorySettings}
                includeSources={exportIncludeSources}
                includeSandbox={exportIncludeSandbox}
                busy={exportBusy}
                message={exportMessage}
                downloadUrl={exportDownloadUrl}
                filename={exportFilename}
                summary={exportSummary}
                onIncludeSourcesChange={setExportIncludeSources}
                onIncludeSandboxChange={setExportIncludeSandbox}
                onExport={() => void exportRepositoryBundle()}
              />
            ) : activeView === "recreate" ? (
              <RecreateRepository
                file={recreateFile}
                repositoryName={recreateRepositoryName}
                targetRepositoryId={recreateTargetRepositoryId}
                availableModels={recreateAvailableModels}
                sourceMappings={recreateSourceMappings}
                validation={recreateValidation}
                result={recreateResult}
                busy={recreateBusy}
                message={recreateMessage}
                onFileChange={(file) => {
                  setRecreateFile(file);
                  setRecreateValidation(null);
                  setRecreateResult(null);
                  setRecreateMessage(file ? "Ready to validate bundle" : "Select an export ZIP bundle");
                }}
                onRepositoryNameChange={setRecreateRepositoryName}
                onTargetRepositoryIdChange={setRecreateTargetRepositoryId}
                onAvailableModelsChange={setRecreateAvailableModels}
                onSourceMappingsChange={setRecreateSourceMappings}
                onValidate={() => void validateRecreateBundle()}
                onRecreate={() => void runRecreateBundle()}
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
                                    <div className="row table-actions">
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
                                      <button
                                        className="btn btn-sm btn-ghost danger-action"
                                        type="button"
                                        onClick={() => void deleteDocument(document.id)}
                                        disabled={busy}
                                      >
                                        Delete
                                      </button>
                                    </div>
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

function PromptSandbox({
  prompts,
  selectedPromptId,
  promptName,
  promptBody,
  query,
  model,
  topK,
  comparison,
  progressRuns,
  busy,
  message,
  onSelectPrompt,
  onPromptNameChange,
  onPromptBodyChange,
  onQueryChange,
  onModelChange,
  onTopKChange,
  onSavePrompt,
  onDeletePrompt,
  onRunComparison,
  onOpenContext,
}: {
  prompts: SandboxPromptVersion[];
  selectedPromptId: string | null;
  promptName: string;
  promptBody: string;
  query: string;
  model: string;
  topK: number;
  comparison: SandboxComparison | null;
  progressRuns: SandboxProgressRun[];
  busy: boolean;
  message: string;
  onSelectPrompt: (value: string) => void;
  onPromptNameChange: (value: string) => void;
  onPromptBodyChange: (value: string) => void;
  onQueryChange: (value: string) => void;
  onModelChange: (value: string) => void;
  onTopKChange: (value: number) => void;
  onSavePrompt: () => void;
  onDeletePrompt: () => void;
  onRunComparison: () => void;
  onOpenContext: (result: RetrievalSearchResult) => void;
}) {
  const visibleProgressRuns =
    progressRuns.length > 0
      ? progressRuns
      : comparison
        ? progressRunsFromCompletedRuns(comparison.runs)
        : [];

  return (
    <div className="sandbox-layout">
      <section className="sandbox-controls">
        <div className="card">
          <div className="row row-between">
            <div>
              <div className="eyebrow">Prompt version</div>
              <h2>Sandbox prompt</h2>
            </div>
            <div className="row sandbox-prompt-actions">
              <button className="btn btn-sm" type="button" onClick={onSavePrompt} disabled={busy}>
                Save version
              </button>
              <button
                className="btn btn-sm btn-ghost"
                type="button"
                onClick={onDeletePrompt}
                disabled={busy || !selectedPromptId}
              >
                Delete version
              </button>
            </div>
          </div>
          <div className="grid grid-2 sandbox-form">
            <div>
              <label className="field" htmlFor="sandbox-prompt-select">
                Saved versions
              </label>
              <select
                id="sandbox-prompt-select"
                value={selectedPromptId ?? ""}
                onChange={(event) => onSelectPrompt(event.target.value)}
              >
                <option value="">Unsaved draft</option>
                {prompts.map((prompt) => (
                  <option value={prompt.id} key={prompt.id}>
                    {prompt.name}
                  </option>
                ))}
              </select>
            </div>
            <div>
              <label className="field" htmlFor="sandbox-prompt-name">
                Version name
              </label>
              <input
                id="sandbox-prompt-name"
                value={promptName}
                onChange={(event) => onPromptNameChange(event.target.value)}
              />
            </div>
          </div>
          <label className="field" htmlFor="sandbox-prompt-body">
            System prompt
          </label>
          <textarea
            id="sandbox-prompt-body"
            rows={6}
            value={promptBody}
            onChange={(event) => onPromptBodyChange(event.target.value)}
          />
          <p className="hint">
            Sandbox prompt versions are isolated from Chat Workspace defaults. Saving, deleting, or
            running sandbox prompts will not change normal chat behavior.
          </p>
        </div>

        <div className="card">
          <div className="row row-between">
            <div>
              <div className="eyebrow">Comparison setup</div>
              <h2>Four retrieval modes</h2>
            </div>
            <button
              className={`btn btn-primary ${busy ? "btn-running" : ""}`}
              type="button"
              onClick={onRunComparison}
              disabled={busy}
              aria-busy={busy}
            >
              {busy ? "Running comparison..." : "Run comparison"}
            </button>
          </div>
          <div className="grid grid-3 sandbox-form">
            <div>
              <label className="field" htmlFor="sandbox-query">
                Query
              </label>
              <input
                id="sandbox-query"
                value={query}
                onChange={(event) => onQueryChange(event.target.value)}
              />
            </div>
            <div>
              <label className="field" htmlFor="sandbox-model">
                Local model
              </label>
              <input
                id="sandbox-model"
                value={model}
                onChange={(event) => onModelChange(event.target.value)}
              />
            </div>
            <div>
              <label className="field" htmlFor="sandbox-top-k">
                Top-k
              </label>
              <select
                id="sandbox-top-k"
                value={topK}
                onChange={(event) => onTopKChange(Number(event.target.value))}
              >
                {[3, 5, 6, 10].map((value) => (
                  <option value={value} key={value}>
                    {value}
                  </option>
                ))}
              </select>
            </div>
          </div>
          <div className="sandbox-presets">
            {sandboxComparisonRunConfigs("preview", model, topK).map((run) => (
              <span className="badge" key={run.label}>
                <span className="dot" />
                {run.label}
              </span>
            ))}
          </div>
          <p className="hint">{message}</p>
        </div>
      </section>

      {visibleProgressRuns.length > 0 ? (
        <section className="sandbox-results">
          <div className="row row-between">
            <div>
              <div className="eyebrow">Comparison results</div>
              <h2>{comparison?.query ?? query}</h2>
            </div>
            <span className="badge badge-ok">
              <span className="dot" />
              {comparison?.status ?? "running"}
            </span>
          </div>
          <div className="sandbox-run-grid">
            {visibleProgressRuns.map((progressRun) => (
              <SandboxRunCard
                progressRun={progressRun}
                key={progressRun.id}
                onOpenContext={onOpenContext}
              />
            ))}
          </div>
        </section>
      ) : (
        <div className="empty">
          <h3>No comparison yet</h3>
          <p>Run the four-mode comparison to see answers, settings, latency, and retrieved context side by side.</p>
        </div>
      )}
    </div>
  );
}

function ExportCenter({
  repository,
  documents,
  totalChunks,
  chatSessions,
  sandboxPrompts,
  settings,
  includeSources,
  includeSandbox,
  busy,
  message,
  downloadUrl,
  filename,
  summary,
  onIncludeSourcesChange,
  onIncludeSandboxChange,
  onExport,
}: {
  repository: RepositoryResponse["repository"] | null;
  documents: DocumentSummary[];
  totalChunks: number;
  chatSessions: ChatSession[];
  sandboxPrompts: SandboxPromptVersion[];
  settings: RepositorySettings | null;
  includeSources: boolean;
  includeSandbox: boolean;
  busy: boolean;
  message: string;
  downloadUrl: string | null;
  filename: string | null;
  summary: ExportManifestSummary | null;
  onIncludeSourcesChange: (value: boolean) => void;
  onIncludeSandboxChange: (value: boolean) => void;
  onExport: () => void;
}) {
  const chatMessageCount = chatSessions.reduce((sum, session) => sum + session.messages.length, 0);
  const chatCitationCount = chatSessions.reduce(
    (sum, session) =>
      sum + session.messages.reduce((messageSum, chatMessage) => messageSum + chatMessage.citations.length, 0),
    0,
  );
  const promptCount = settings?.prompt.library.length ?? 0;
  const requiredModels = requiredModelsForSettings(settings);
  const settingsRows = settingsSummaryRows(settings);

  return (
    <div className="export-layout">
      <section className="card export-overview">
        <div className="row row-between">
          <div>
            <div className="eyebrow">Repository export</div>
            <h2>{repository?.name ?? "Default Repository"}</h2>
          </div>
          <span className={`badge ${downloadUrl ? "badge-ok" : busy ? "badge-running" : ""}`}>
            <span className="dot" />
            {message}
          </span>
        </div>
        <div className="export-metrics">
          <ExportMetric label="Sources" value={documents.length} />
          <ExportMetric label="Chunks" value={totalChunks} />
          <ExportMetric label="Chat sessions" value={chatSessions.length} />
          <ExportMetric label="Chat messages" value={chatMessageCount} />
          <ExportMetric label="Citations" value={chatCitationCount} />
          <ExportMetric label="Prompt data" value={promptCount + sandboxPrompts.length} />
          <ExportMetric label="Retrieval runs" value={summary?.counts.retrieval_runs ?? "after export"} />
          <ExportMetric label="Sandbox runs" value={summary?.counts.sandbox_runs ?? (includeSandbox ? "included" : "excluded")} />
        </div>
      </section>

      <div className="export-grid">
        <section className="card">
          <div className="row row-between">
            <div>
              <div className="eyebrow">Bundle options</div>
              <h2>ZIP contents</h2>
            </div>
            <button
              className={`btn btn-primary ${busy ? "btn-running" : ""}`}
              type="button"
              onClick={onExport}
              disabled={busy || !repository}
              aria-busy={busy}
            >
              {busy ? "Exporting..." : "Export ZIP"}
            </button>
          </div>
          <div className="export-option-list">
            <label className="export-toggle" htmlFor="export-include-sources">
              <input
                id="export-include-sources"
                type="checkbox"
                checked={includeSources}
                onChange={(event) => onIncludeSourcesChange(event.target.checked)}
              />
              <span>
                <strong>Include source files</strong>
                <small>{includeSources ? `${documents.length} files will be packaged` : "Hashes and paths only"}</small>
              </span>
            </label>
            <label className="export-toggle" htmlFor="export-include-sandbox">
              <input
                id="export-include-sandbox"
                type="checkbox"
                checked={includeSandbox}
                onChange={(event) => onIncludeSandboxChange(event.target.checked)}
              />
              <span>
                <strong>Include sandbox runs/comparisons</strong>
                <small>{includeSandbox ? "Sandbox history will be packaged" : "Default export excludes sandbox runs"}</small>
              </span>
            </label>
          </div>
          {downloadUrl && (
            <div className="export-download">
              <a className="btn" href={downloadUrl} download={filename ?? "repository-export.zip"}>
                Download ZIP
              </a>
              <span className="muted">{filename ?? "repository-export.zip"}</span>
            </div>
          )}
        </section>

        <section className="card">
          <div className="eyebrow">Models and settings</div>
          <h2>Required setup</h2>
          <dl className="kv export-kv">
            {settingsRows.map((row) => (
              <React.Fragment key={row.label}>
                <dt>{row.label}</dt>
                <dd>{row.value}</dd>
              </React.Fragment>
            ))}
          </dl>
          <div className="export-chip-list">
            {requiredModels.length > 0 ? (
              requiredModels.map((model) => (
                <span className="badge" key={model}>
                  <span className="dot" />
                  {model}
                </span>
              ))
            ) : (
              <span className="muted">Settings unavailable</span>
            )}
          </div>
        </section>
      </div>

      {summary && (
        <section className="card export-summary">
          <div className="row row-between">
            <div>
              <div className="eyebrow">Manifest summary</div>
              <h2>{summary.repository.name}</h2>
            </div>
            <span className="badge badge-ok">
              <span className="dot" />
              {new Date(summary.generated_at).toLocaleString()}
            </span>
          </div>
          <div className="export-metrics">
            {Object.entries(summary.counts).map(([label, value]) => (
              <ExportMetric label={label.replace(/_/g, " ")} value={value} key={label} />
            ))}
          </div>
          <dl className="kv export-kv">
            <dt>sources</dt>
            <dd>{summary.export_options.include_sources ? "included" : "excluded"}</dd>
            <dt>sandbox</dt>
            <dd>{summary.export_options.include_sandbox ? "included" : "excluded"}</dd>
            <dt>format</dt>
            <dd>{summary.export_options.format}</dd>
          </dl>
        </section>
      )}
    </div>
  );
}

function ExportMetric({ label, value }: { label: string; value: number | string }) {
  return (
    <div className="export-metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function RecreateRepository({
  file,
  repositoryName,
  targetRepositoryId,
  availableModels,
  sourceMappings,
  validation,
  result,
  busy,
  message,
  onFileChange,
  onRepositoryNameChange,
  onTargetRepositoryIdChange,
  onAvailableModelsChange,
  onSourceMappingsChange,
  onValidate,
  onRecreate,
}: {
  file: File | null;
  repositoryName: string;
  targetRepositoryId: string;
  availableModels: string;
  sourceMappings: RecreateSourceMapping[];
  validation: ExportBundleValidationResponse | null;
  result: RecreateBundleResponse | null;
  busy: "validating" | "recreating" | null;
  message: string;
  onFileChange: (file: File | null) => void;
  onRepositoryNameChange: (value: string) => void;
  onTargetRepositoryIdChange: (value: string) => void;
  onAvailableModelsChange: (value: string) => void;
  onSourceMappingsChange: (value: RecreateSourceMapping[]) => void;
  onValidate: () => void;
  onRecreate: () => void;
}) {
  const canRecreate = Boolean(file && validation?.can_recreate && !busy);
  const statusClass = result?.status === "completed" ? "badge-ok" : validation?.can_recreate ? "badge-ok" : validation ? "badge-danger" : "";
  const steps = recreateProgressSteps(validation, result, busy);

  return (
    <div className="recreate-layout">
      <section className="card recreate-overview">
        <div className="row row-between">
          <div>
            <div className="eyebrow">Bundle recreate</div>
            <h2>{file?.name ?? "No bundle selected"}</h2>
          </div>
          <span className={`badge ${busy ? "badge-running" : statusClass}`}>
            <span className="dot" />
            {message}
          </span>
        </div>
        <div className="recreate-steps">
          {steps.map((step) => (
            <div className={`recreate-step recreate-step-${step.status}`} key={step.label}>
              <span>{step.label}</span>
              <strong>{step.status}</strong>
            </div>
          ))}
        </div>
      </section>

      <div className="recreate-grid">
        <section className="card">
          <div className="row row-between">
            <div>
              <div className="eyebrow">Validation</div>
              <h2>Bundle and target</h2>
            </div>
            <button
              className={`btn ${busy === "validating" ? "btn-running" : ""}`}
              type="button"
              onClick={onValidate}
              disabled={!file || Boolean(busy)}
              aria-busy={busy === "validating"}
            >
              {busy === "validating" ? "Validating..." : "Validate bundle"}
            </button>
          </div>
          <div className="grid grid-2 recreate-form">
            <label className="field" htmlFor="recreate-bundle-file">
              Bundle ZIP
              <input
                id="recreate-bundle-file"
                type="file"
                accept=".zip,application/zip"
                onChange={(event) => onFileChange(event.target.files?.[0] ?? null)}
              />
            </label>
            <label className="field" htmlFor="recreate-repository-name">
              New repository name
              <input
                id="recreate-repository-name"
                value={repositoryName}
                onChange={(event) => onRepositoryNameChange(event.target.value)}
              />
            </label>
            <label className="field" htmlFor="recreate-target-repository-id">
              Existing empty repository ID
              <input
                id="recreate-target-repository-id"
                value={targetRepositoryId}
                onChange={(event) => onTargetRepositoryIdChange(event.target.value)}
              />
            </label>
            <label className="field" htmlFor="recreate-available-models">
              Available models
              <input
                id="recreate-available-models"
                value={availableModels}
                onChange={(event) => onAvailableModelsChange(event.target.value)}
              />
            </label>
          </div>
          <div className="row recreate-actions">
            <button
              className={`btn btn-primary ${busy === "recreating" ? "btn-running" : ""}`}
              type="button"
              onClick={onRecreate}
              disabled={!canRecreate}
              aria-busy={busy === "recreating"}
            >
              {busy === "recreating" ? "Recreating..." : "Recreate repository"}
            </button>
            {validation && (
              <span className={validation.can_recreate ? "badge badge-ok" : "badge badge-danger"}>
                <span className="dot" />
                {validation.can_recreate ? "ready" : "blocked"}
              </span>
            )}
          </div>
        </section>

        <section className="card">
          <div className="eyebrow">Source mappings</div>
          <h2>External files</h2>
          <div className="recreate-mapping-list">
            {sourceMappings.length === 0 ? (
              <p className="muted">No external source mappings requested.</p>
            ) : (
              sourceMappings.map((mapping, index) => (
                <div className="recreate-mapping-row" key={`${mapping.sha256}-${mapping.document_version_id ?? index}`}>
                  <label className="field" htmlFor={`recreate-mapping-sha-${index}`}>
                    Source hash
                    <input
                      id={`recreate-mapping-sha-${index}`}
                      value={mapping.sha256}
                      onChange={(event) =>
                        onSourceMappingsChange(
                          sourceMappings.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, sha256: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </label>
                  <label className="field" htmlFor={`recreate-mapping-path-${index}`}>
                    Local path
                    <input
                      id={`recreate-mapping-path-${index}`}
                      value={mapping.path}
                      onChange={(event) =>
                        onSourceMappingsChange(
                          sourceMappings.map((item, itemIndex) =>
                            itemIndex === index ? { ...item, path: event.target.value } : item,
                          ),
                        )
                      }
                    />
                  </label>
                  <button
                    className="btn btn-sm btn-ghost"
                    type="button"
                    onClick={() => onSourceMappingsChange(sourceMappings.filter((_, itemIndex) => itemIndex !== index))}
                  >
                    Remove
                  </button>
                </div>
              ))
            )}
          </div>
          <button
            className="btn btn-sm"
            type="button"
            onClick={() => onSourceMappingsChange([...sourceMappings, { sha256: "", path: "" }])}
          >
            Add mapping
          </button>
        </section>
      </div>

      {validation && (
        <section className="card recreate-report">
          <div className="row row-between">
            <div>
              <div className="eyebrow">Validation report</div>
              <h2>{validation.manifest ? manifestRepositoryName(validation.manifest) : "Bundle report"}</h2>
            </div>
            <div className="export-chip-list">
              {validation.required_models.map((model) => (
                <span className="badge" key={model}>
                  <span className="dot" />
                  {model}
                </span>
              ))}
            </div>
          </div>
          <div className="export-metrics">
            {Object.entries(validation.counts).map(([label, value]) => (
              <ExportMetric label={label.replace(/_/g, " ")} value={value} key={label} />
            ))}
          </div>
          <div className="recreate-issue-grid">
            <IssueGroup title="Blocking errors" issues={validation.blocking_errors} emptyLabel="No blocking errors" />
            <IssueGroup title="Warnings" issues={validation.warnings} emptyLabel="No warnings" />
            <IssueGroup title="Information" issues={validation.informational} emptyLabel="No informational checks" />
          </div>
        </section>
      )}

      {result && (
        <section className="card recreate-report">
          <div className="row row-between">
            <div>
              <div className="eyebrow">Final report</div>
              <h2>{result.repository_name ?? "Recreated repository"}</h2>
            </div>
            <span className={result.status === "completed" ? "badge badge-ok" : "badge badge-danger"}>
              <span className="dot" />
              {result.status}
            </span>
          </div>
          <div className="export-metrics">
            {Object.entries(result.restored_counts).map(([label, value]) => (
              <ExportMetric label={label.replace(/_/g, " ")} value={value} key={label} />
            ))}
            <ExportMetric label="full-text index" value={result.indexes.full_text_indexed_chunks} />
            <ExportMetric label="vector index" value={result.indexes.vector_indexed_chunks} />
          </div>
          <dl className="kv export-kv">
            <dt>repository</dt>
            <dd>{result.repository_id ?? "not created"}</dd>
            <dt>vector collection</dt>
            <dd>{result.indexes.vector_collection_name ?? "not rebuilt"}</dd>
            <dt>vector model</dt>
            <dd>{result.indexes.vector_model ?? "not reported"}</dd>
          </dl>
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Source</th>
                  <th>Status</th>
                  <th>Expected chunks</th>
                  <th>Actual chunks</th>
                </tr>
              </thead>
              <tbody>
                {result.sources.map((source) => (
                  <tr key={source.original_document_version_id}>
                    <td>{source.original_filename}</td>
                    <td>{source.status}</td>
                    <td className="num">{source.expected_chunk_count}</td>
                    <td className="num">{source.actual_chunk_count}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}
    </div>
  );
}

function IssueGroup({
  title,
  issues,
  emptyLabel,
}: {
  title: string;
  issues: ExportBundleValidationIssue[];
  emptyLabel: string;
}) {
  return (
    <div className="recreate-issue-group">
      <h3>{title}</h3>
      {issues.length === 0 ? (
        <p className="muted">{emptyLabel}</p>
      ) : (
        issues.map((issue) => (
          <article className={`recreate-issue recreate-issue-${issue.severity}`} key={`${issue.code}-${issue.path ?? issue.source_sha256 ?? issue.message}`}>
            <strong>{issueLabel(issue.code)}</strong>
            <span>{issue.message}</span>
            {(issue.path || issue.setting || issue.source_sha256) && (
              <small>
                {[issue.path, issue.setting, issue.source_sha256 ? shortHash(issue.source_sha256) : null]
                  .filter(Boolean)
                  .join(" · ")}
              </small>
            )}
          </article>
        ))
      )}
    </div>
  );
}

function SandboxRunCard({
  progressRun,
  onOpenContext,
}: {
  progressRun: SandboxProgressRun;
  onOpenContext: (result: RetrievalSearchResult) => void;
}) {
  const run = progressRun.run;
  const firstContext = run?.context_entries[0] ?? null;
  return (
    <article className={`sandbox-run-card sandbox-run-card-${progressRun.status}`}>
      <div className="row row-between">
        <div>
          <div className="eyebrow">{progressRun.label}</div>
          <h3>{sandboxModeLabel(progressRun.retrieval_settings)}</h3>
        </div>
        <span className={`badge badge-${progressRun.status}`}>
          <span className="dot" />
          {run ? formatLatencySeconds(run.latency_ms) : progressRun.status}
        </span>
      </div>
      <p className="sandbox-answer">
        {run?.answer ??
          (progressRun.status === "failed"
            ? (progressRun.error ?? "This retrieval mode failed.")
            : progressRun.status === "running"
              ? "Running this retrieval mode..."
              : "Waiting to start...")}
      </p>
      <dl className="kv sandbox-kv">
        <dt>model</dt>
        <dd>{run?.model ?? progressRun.model}</dd>
        <dt>prompt</dt>
        <dd>{run ? sandboxPromptSnapshotName(run.prompt_snapshot) : "pending"}</dd>
        <dt>top-k</dt>
        <dd>{progressRun.retrieval_settings.top_k}</dd>
        <dt>context</dt>
        <dd>{run?.context_entries.length ?? "—"}</dd>
        <dt>citations</dt>
        <dd>{run?.citations.length ?? "—"}</dd>
        <dt>run</dt>
        <dd>{run ? (run.retrieval_run_id?.slice(0, 8) ?? run.id.slice(0, 8)) : progressRun.status}</dd>
      </dl>
      <div className="stack sandbox-context">
        {(run?.context_entries ?? []).slice(0, 2).map((entry) => (
          <div className="source-card" key={`${progressRun.id}-${entry.chunk_id}`}>
            <div className="meta">
              #{entry.rank} · {entry.document_title} · {searchProvenanceLabel(entry)} · final{" "}
              {entry.final_score.toFixed(4)}
            </div>
            <p>{entry.text_preview || entry.snippet || "No preview available."}</p>
            <div className="row row-between">
              <span className="hint">
                BM25 {formatScore(entry.score_breakdown.bm25)} · Dense{" "}
                {formatScore(entry.score_breakdown.dense)} · Rerank{" "}
                {formatScore(entry.score_breakdown.rerank)}
              </span>
              <button className="btn btn-sm btn-ghost" type="button" onClick={() => onOpenContext(entry)}>
                View source
              </button>
            </div>
          </div>
        ))}
        {!firstContext && (
          <p className="muted">
            {progressRun.status === "completed"
              ? "No retrieved context was stored for this run."
              : "Context will appear here when this retrieval mode finishes."}
          </p>
        )}
      </div>
    </article>
  );
}

function ChatWorkspace({
  sessions,
  activeSession,
  input,
  busy,
  message,
  activeCitation,
  retrievalSettings,
  readiness,
  readinessBusy,
  readinessCheckedAt,
  rebuildBusy,
  onInputChange,
  onCreateSession,
  onSelectSession,
  onDeleteSession,
  onClearSessions,
  onAsk,
  onRetrievalSettingsChange,
  onRebuildFullText,
  onRebuildVector,
  onCheckReadiness,
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
  retrievalSettings: ChatRetrievalSettings;
  readiness: ChatReadiness | null;
  readinessBusy: boolean;
  readinessCheckedAt: string | null;
  rebuildBusy: "full-text" | "vector" | null;
  onInputChange: (value: string) => void;
  onCreateSession: () => void;
  onSelectSession: (value: string) => void;
  onDeleteSession: (value: string) => void;
  onClearSessions: () => void;
  onAsk: () => void;
  onRetrievalSettingsChange: (value: ChatRetrievalSettings) => void;
  onRebuildFullText: () => void;
  onRebuildVector: () => void;
  onCheckReadiness: () => void;
  onCitationClick: (citation: ChatCitation) => void;
  onCloseCitation: () => void;
  onOpenCitation: (citation: ChatCitation) => void;
}) {
  const threadRef = useRef<HTMLDivElement | null>(null);
  const readyForSelectedMode = chatReadyForSelectedMode(readiness, retrievalSettings);

  useEffect(() => {
    const thread = threadRef.current;
    if (thread) {
      thread.scrollTop = thread.scrollHeight;
    }
  }, [activeSession?.messages.length, busy]);

  return (
    <>
      <div className="chat-layout">
        <aside className="chat-side">
          <div className="card card-pad-sm session-list">
            <div className="row row-between session-head">
              <div className="eyebrow">Sessions</div>
              <div className="row session-actions">
                <button className="btn btn-sm btn-ghost" type="button" onClick={onCreateSession} disabled={busy}>
                  New
                </button>
                <button
                  className="btn btn-sm btn-ghost danger-action"
                  type="button"
                  onClick={onClearSessions}
                  disabled={busy || sessions.length === 0}
                >
                  Clear all
                </button>
              </div>
            </div>
            {sessions.length > 0 ? (
              sessions.map((session) => (
                <div
                  className={session.id === activeSession?.id ? "session-item active" : "session-item"}
                  key={session.id}
                >
                  <button type="button" onClick={() => onSelectSession(session.id)}>
                    <span>{session.title}</span>
                    <small>
                      {formatDate(session.updated_at)} · {session.messages.length} msgs
                    </small>
                  </button>
                  <button
                    className="session-delete"
                    type="button"
                    onClick={() => onDeleteSession(session.id)}
                    disabled={busy}
                    aria-label={`Delete ${session.title}`}
                  >
                    x
                  </button>
                </div>
              ))
            ) : (
              <p className="muted">No saved chats yet.</p>
            )}
          </div>

          <div className="card card-pad-sm chat-settings-panel">
            <div className="row row-between">
              <div>
                <div className="eyebrow">Chat retrieval</div>
                <h2>{readyForSelectedMode ? "Ready for chat" : "Repository context not ready"}</h2>
                <p className="hint chat-check-status">
                  {readinessBusy
                    ? "Checking indexes and local model"
                    : readinessCheckedAt
                      ? `Last checked ${formatTime(readinessCheckedAt)}`
                      : "Run Check to refresh readiness"}
                </p>
              </div>
              <button
                className="btn btn-sm"
                type="button"
                onClick={onCheckReadiness}
                disabled={busy || readinessBusy}
              >
                {readinessBusy ? "Checking" : "Check"}
              </button>
            </div>
            <div className="grid grid-3 chat-settings-controls">
              <div>
                <label className="field" htmlFor="chat-mode">
                  Mode
                </label>
                <select
                  id="chat-mode"
                  value={retrievalSettings.mode}
                  onChange={(event) =>
                    onRetrievalSettingsChange({
                      ...retrievalSettings,
                      mode: event.target.value as ChatRetrievalSettings["mode"],
                    })
                  }
                >
                  <option value="full_text">Full-text</option>
                  <option value="vector">Vector</option>
                  <option value="hybrid">Hybrid</option>
                </select>
              </div>
              <div>
                <label className="field" htmlFor="chat-reranker">
                  Reranker
                </label>
                <select
                  id="chat-reranker"
                  value={retrievalSettings.reranker_strategy}
                  onChange={(event) =>
                    onRetrievalSettingsChange({
                      ...retrievalSettings,
                      reranker_strategy: event.target.value as RerankerStrategy,
                    })
                  }
                >
                  <option value="none">None</option>
                  <option value="cross_encoder">Cross-encoder</option>
                  <option value="metadata_boost">Metadata boost</option>
                  <option value="cross_encoder_metadata_boost">Cross-encoder + metadata boost</option>
                </select>
              </div>
              <div>
                <label className="field" htmlFor="chat-top-k">
                  Top-k
                </label>
                <select
                  id="chat-top-k"
                  value={retrievalSettings.top_k}
                  onChange={(event) =>
                    onRetrievalSettingsChange({
                      ...retrievalSettings,
                      top_k: Number(event.target.value),
                    })
                  }
                >
                  {[3, 5, 6, 10, 20].map((value) => (
                    <option value={value} key={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
            </div>
            <div className="readiness-grid" data-parsed-chunks={readiness?.parsed_chunks ?? 0}>
              <ReadinessPill label="Full-text" item={readiness?.full_text ?? null} />
              <ReadinessPill label="Vector" item={readiness?.vector ?? null} />
              <ReadinessPill label="Local model" item={readiness?.local_model ?? null} />
            </div>
            <div className="row chat-index-actions">
              <button
                className="btn btn-sm"
                type="button"
                onClick={onRebuildFullText}
                disabled={busy || rebuildBusy !== null || (readiness?.parsed_chunks ?? 0) === 0}
              >
                {rebuildBusy === "full-text" ? "Rebuilding full-text" : "Rebuild full-text"}
              </button>
              <button
                className="btn btn-sm"
                type="button"
                onClick={onRebuildVector}
                disabled={busy || rebuildBusy !== null || (readiness?.parsed_chunks ?? 0) === 0}
              >
                {rebuildBusy === "vector" ? "Rebuilding vector" : "Rebuild vector"}
              </button>
              <span className="muted">
                {activeSession?.model ?? "gemma3:4b"} · settings are saved on send
              </span>
            </div>
          </div>
        </aside>

        <section className="chat-main">
          <div
            className={activeSession?.messages.length || busy ? "chat-thread" : "chat-thread chat-thread-empty"}
            ref={threadRef}
          >
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
            {busy && (
              <div className="msg assistant thinking">
                <div className="eyebrow">Local model</div>
                <p>Retrieving context and composing an answer</p>
                <div className="thinking-dots" aria-label="Local LLM is thinking">
                  <span />
                  <span />
                  <span />
                </div>
              </div>
            )}
          </div>

          <div className="chat-composer">
            <div className="chat-input">
              <textarea
                rows={2}
                value={input}
                onChange={(event) => onInputChange(event.target.value)}
                onKeyDown={(event) => {
                  if (
                    event.key === "Enter" &&
                    !event.shiftKey &&
                    !event.nativeEvent.isComposing
                  ) {
                    event.preventDefault();
                    onAsk();
                  }
                }}
                placeholder="Ask a question grounded in this repository..."
                disabled={busy}
              />
              <button className="btn btn-primary" type="button" onClick={onAsk} disabled={busy || !input.trim()}>
                {busy ? "Sending" : "Send"}
              </button>
            </div>
            <p className="hint">{busy ? "Local model is still working..." : message}</p>
          </div>
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
              {activeCitation.text_preview && (
                <p
                  className="citation-preview"
                  dangerouslySetInnerHTML={{ __html: activeCitation.text_preview }}
                />
              )}
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

function ReadinessPill({ label, item }: { label: string; item: ChatReadinessItem | null }) {
  const ready = item?.ready === true;
  const status = item?.status ?? "missing";
  const statusLabel = status === "partial" ? "Partial" : status === "stale" ? "Stale" : ready ? "Ready" : "Needed";
  return (
    <div className={`readiness-pill ${status}`} data-readiness-status={status}>
      <span>{label}</span>
      <b>{statusLabel}</b>
      <small>{item?.message ?? "Not checked yet"}</small>
    </div>
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

function formatTime(value: string) {
  return new Intl.DateTimeFormat(undefined, {
    hour: "numeric",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

function chatReadyForSelectedMode(
  readiness: ChatReadiness | null,
  settings: ChatRetrievalSettings,
) {
  if (!readiness || readiness.parsed_chunks <= 0 || !readiness.local_model.ready) {
    return false;
  }
  if (settings.mode === "full_text") {
    return readiness.full_text.ready;
  }
  if (settings.mode === "vector") {
    return readiness.vector.ready;
  }
  return readiness.full_text.ready && readiness.vector.ready;
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

function normalizeChatRetrievalSettings(settings: Partial<ChatRetrievalSettings>): ChatRetrievalSettings {
  return {
    mode: settings.mode ?? "hybrid",
    top_k: settings.top_k ?? 6,
    reranker_strategy: settings.reranker_strategy ?? "cross_encoder",
  };
}

function sandboxComparisonRunConfigs(
  promptVersionId: string,
  model: string,
  topK: number,
): Array<{
  label: string;
  prompt_version_id: string;
  model: string;
  retrieval_settings: ChatRetrievalSettings;
}> {
  return [
    {
      label: "Full-text",
      prompt_version_id: promptVersionId,
      model,
      retrieval_settings: {
        mode: "full_text",
        top_k: topK,
        reranker_strategy: "none",
      },
    },
    {
      label: "Vector",
      prompt_version_id: promptVersionId,
      model,
      retrieval_settings: {
        mode: "vector",
        top_k: topK,
        reranker_strategy: "none",
      },
    },
    {
      label: "Hybrid",
      prompt_version_id: promptVersionId,
      model,
      retrieval_settings: {
        mode: "hybrid",
        top_k: topK,
        reranker_strategy: "none",
      },
    },
    {
      label: "Reranked hybrid",
      prompt_version_id: promptVersionId,
      model,
      retrieval_settings: {
        mode: "hybrid",
        top_k: topK,
        reranker_strategy: "cross_encoder",
      },
    },
  ];
}

function progressRunsFromConfigs(
  runConfigs: SandboxComparisonRunConfig[],
  status: SandboxProgressRun["status"],
): SandboxProgressRun[] {
  return runConfigs.map((runConfig) => ({
    id: runConfig.label,
    label: runConfig.label,
    model: runConfig.model,
    retrieval_settings: runConfig.retrieval_settings,
    status,
    run: null,
    error: null,
  }));
}

function progressRunsFromCompletedRuns(runs: SandboxRun[]): SandboxProgressRun[] {
  return runs.map((run) => ({
    id: run.id,
    label: run.label ?? `Run ${(run.comparison_index ?? 0) + 1}`,
    model: run.model,
    retrieval_settings: run.retrieval_settings,
    status: run.status === "completed" ? "completed" : "failed",
    run,
    error: run.status === "completed" ? null : "This retrieval mode failed.",
  }));
}

function sandboxModeLabel(settings: ChatRetrievalSettings) {
  const mode = settings.mode === "full_text" ? "Full-text" : settings.mode === "vector" ? "Vector" : "Hybrid";
  if (settings.reranker_strategy === "none") {
    return mode;
  }
  return `${mode} · ${settings.reranker_strategy.replace(/_/g, " ")}`;
}

function formatScore(value: number | null | undefined) {
  return value == null ? "—" : value.toFixed(4);
}

function formatLatencySeconds(latencyMs: number) {
  return `${(latencyMs / 1000).toFixed(1)} s`;
}

function sandboxPromptSnapshotName(snapshot: Record<string, unknown>) {
  return typeof snapshot.name === "string" && snapshot.name.trim() ? snapshot.name : "Snapshot";
}

function filenameFromContentDisposition(header: string | null) {
  if (!header) {
    return null;
  }
  const match = header.match(/filename="?([^";]+)"?/i);
  return match?.[1] ?? null;
}

function requiredModelsForSettings(settings: RepositorySettings | null) {
  if (!settings) {
    return [];
  }
  return Array.from(
    new Set(
      [
        settings.model.ollama_chat_model,
        settings.embedding.model,
        settings.reranking.model,
      ].filter((model): model is string => Boolean(model)),
    ),
  );
}

function settingsSummaryRows(settings: RepositorySettings | null) {
  if (!settings) {
    return [{ label: "settings", value: "unavailable" }];
  }
  return [
    { label: "chat model", value: settings.model.ollama_chat_model },
    { label: "embedding", value: `${settings.embedding.provider} / ${settings.embedding.model}` },
    {
      label: "reranking",
      value: settings.reranking.model
        ? `${settings.reranking.strategy} / ${settings.reranking.model}`
        : settings.reranking.strategy,
    },
    { label: "chunking", value: `${settings.chunking.mode} ${settings.chunking.chunk_size}/${settings.chunking.chunk_overlap}` },
    { label: "full-text", value: settings.full_text.tokenizer },
    { label: "parser", value: settings.parser.structured_parser },
  ];
}

function buildExportManifestSummary({
  repository,
  documents,
  totalChunks,
  chatSessions,
  sandboxPrompts,
  settings,
  includeSources,
  includeSandbox,
}: {
  repository: RepositoryResponse["repository"];
  documents: DocumentSummary[];
  totalChunks: number;
  chatSessions: ChatSession[];
  sandboxPrompts: SandboxPromptVersion[];
  settings: RepositorySettings | null;
  includeSources: boolean;
  includeSandbox: boolean;
}): ExportManifestSummary {
  const chatMessages = chatSessions.reduce((sum, session) => sum + session.messages.length, 0);
  const chatCitations = chatSessions.reduce(
    (sum, session) =>
      sum + session.messages.reduce((messageSum, chatMessage) => messageSum + chatMessage.citations.length, 0),
    0,
  );
  const promptCount = settings?.prompt.library.length ?? 0;
  return {
    generated_at: new Date().toISOString(),
    repository,
    export_options: {
      include_sources: includeSources,
      include_sandbox: includeSandbox,
      format: settings?.export.format ?? "json",
    },
    counts: {
      sources: documents.length,
      included_sources: includeSources ? documents.length : 0,
      chunks: totalChunks,
      chat_sessions: chatSessions.length,
      chat_messages: chatMessages,
      chat_citations: chatCitations,
      prompt_library_entries: promptCount,
      sandbox_prompt_versions: sandboxPrompts.length,
      sandbox_runs: includeSandbox ? sandboxPrompts.filter((prompt) => prompt.used_by_run).length : 0,
      retrieval_runs: chatCitations,
    },
    required_models: requiredModelsForSettings(settings),
    settings_summary: settingsSummaryRows(settings).map((row) => `${row.label}: ${row.value}`),
    warnings: [],
  };
}

function recreateFormData(
  file: File,
  options: {
    repositoryName?: string;
    targetRepositoryId?: string;
    availableModelsText: string;
    sourceMappings: RecreateSourceMapping[];
  },
) {
  const formData = new FormData();
  formData.append("file", file);
  const repositoryName = options.repositoryName?.trim();
  const targetRepositoryId = options.targetRepositoryId?.trim();
  const availableModels = parseAvailableModels(options.availableModelsText);
  const sourceMappings = normalizeSourceMappings(options.sourceMappings);
  if (availableModels.length > 0) {
    formData.append("available_models_json", JSON.stringify(availableModels));
  }
  if (repositoryName) {
    formData.append("repository_name", repositoryName);
  }
  if (targetRepositoryId) {
    formData.append("target_repository_id", targetRepositoryId);
  }
  if (sourceMappings.length > 0) {
    formData.append("source_mappings_json", JSON.stringify(sourceMappings));
  }
  return formData;
}

function parseAvailableModels(value: string) {
  return value
    .split(/[\n,]+/)
    .map((model) => model.trim())
    .filter(Boolean);
}

function normalizeSourceMappings(sourceMappings: RecreateSourceMapping[]) {
  return sourceMappings
    .map((mapping) => ({
      sha256: mapping.sha256.trim(),
      path: mapping.path.trim(),
      document_version_id: mapping.document_version_id?.trim() || undefined,
    }))
    .filter((mapping) => mapping.sha256 && mapping.path);
}

function mergeRepositories(current: RepositoryRead[], repository: RepositoryRead) {
  const repositoriesById = new Map(current.map((item) => [item.id, item]));
  repositoriesById.set(repository.id, { ...repositoriesById.get(repository.id), ...repository });
  return Array.from(repositoriesById.values());
}

function mergeSourceMappings(
  current: RecreateSourceMapping[],
  validation: ExportBundleValidationResponse,
) {
  const existing = new Map(current.map((mapping) => [mapping.sha256, mapping]));
  for (const source of validation.manifest?.sources ?? []) {
    if (!source.included && !existing.has(source.sha256)) {
      existing.set(source.sha256, {
        sha256: source.sha256,
        path: "",
        document_version_id: source.document_version_id,
      });
    }
  }
  for (const issue of validation.blocking_errors) {
    if (issue.code === "missing_external_source_mapping" && issue.source_sha256 && !existing.has(issue.source_sha256)) {
      existing.set(issue.source_sha256, {
        sha256: issue.source_sha256,
        path: "",
        document_version_id: issue.document_version_id ?? undefined,
      });
    }
  }
  return Array.from(existing.values());
}

function recreateProgressSteps(
  validation: ExportBundleValidationResponse | null,
  result: RecreateBundleResponse | null,
  busy: "validating" | "recreating" | null,
) {
  return [
    {
      label: "validation",
      status: busy === "validating" ? "running" : validation ? (validation.can_recreate ? "complete" : "blocked") : "pending",
    },
    {
      label: "source restore",
      status: busy === "recreating" ? "running" : result ? (result.status === "completed" ? "complete" : "failed") : "pending",
    },
    {
      label: "parsing",
      status: busy === "recreating" ? "running" : result?.sources.length ? "complete" : "pending",
    },
    {
      label: "full-text rebuild",
      status: busy === "recreating" ? "running" : result ? (result.indexes.full_text_indexed_chunks > 0 ? "complete" : "warning") : "pending",
    },
    {
      label: "vector rebuild",
      status: busy === "recreating" ? "running" : result ? (result.indexes.vector_indexed_chunks > 0 ? "complete" : "warning") : "pending",
    },
    {
      label: "final report",
      status: busy === "recreating" ? "running" : result ? result.status : "pending",
    },
  ];
}

function manifestRepositoryName(manifest: ExportBundleManifest) {
  return typeof manifest.repository.name === "string" ? manifest.repository.name : "Exported repository";
}

function issueLabel(code: string) {
  const labels: Record<string, string> = {
    missing_payload: "Missing bundle payload",
    source_hash_mismatch: "Source hash mismatch",
    missing_external_source_mapping: "Missing external source mapping",
    external_source_hash_mismatch: "External source hash mismatch",
    external_source_renamed: "External source path changed",
    missing_model: "Missing model",
    unconfirmed_model: "Model not confirmed",
    model_availability_unconfirmed: "Model availability not checked",
    parser_fingerprint: "Parser/settings fingerprint",
    count_mismatch: "Count mismatch",
    source_hash_verified: "Source hash verified",
    external_source_hash_verified: "External source hash verified",
  };
  return labels[code] ?? code.replace(/_/g, " ");
}

function viewFromHash(hash: string): View {
  if (hash === "#recreate-repository") {
    return "recreate";
  }
  if (hash === "#export-center") {
    return "export";
  }
  if (hash === "#chat-workspace") {
    return "chat";
  }
  if (hash === "#prompt-sandbox") {
    return "sandbox";
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
