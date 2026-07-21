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
  ocr: {
    provider: "ocrmypdf_tesseract" | "rapidocr";
    fallback_provider: "none" | "ocrmypdf_tesseract" | "rapidocr";
    fallback_enabled: boolean;
    language: string;
    confidence_threshold: number;
    min_text_length: number;
    max_pages: number;
    overwrite: boolean;
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
  retrieval: RetrievalDefaults;
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

type RepositoryLoadState = {
  repositoryId: string | null;
  status: "empty" | "loading" | "loaded" | "failed";
  message: string;
};

type SettingsImpact = {
  category:
    | "document_reprocessing"
    | "full_text_rebuild"
    | "vector_rebuild"
    | "retrieval_defaults"
    | "chat_defaults"
    | "prompt_defaults"
    | "export_recreate"
    | "evaluation_freshness";
  severity: "info" | "warning";
  title: string;
  message: string;
  fields: string[];
  actions: string[];
};

type SettingsImpactResponse = {
  has_changes: boolean;
  impacts: SettingsImpact[];
};

type SettingsReadinessStatus =
  | "not_checked"
  | "unavailable_runtime"
  | "not_installed"
  | "ready"
  | "failed"
  | "skipped";

type SettingsReadinessItem = {
  target: "qdrant" | "chat" | "embedding" | "reranker";
  label: string;
  status: SettingsReadinessStatus;
  ready: boolean;
  message: string;
  model: string | null;
};

type SettingsReadinessResponse = {
  repository_id: string;
  checked: boolean;
  items: SettingsReadinessItem[];
};

type ModelCatalogSource = "known" | "detected";

type EmbeddingModelCatalogEntry = {
  provider: "sentence_transformers" | "ollama";
  model: string;
  label: string;
  source: ModelCatalogSource;
  vector_size: number;
  supported_distances: string[];
  resource_notes: string;
  setup_hint: string;
  requires_local_model: boolean;
  requires_live_probe: boolean;
};

type ChatModelCatalogEntry = ChatModelInfo & {
  source: ModelCatalogSource;
};

type RerankerModelCatalogEntry = {
  strategy: string;
  model: string | null;
  label: string;
  source: ModelCatalogSource;
  enabled: boolean;
  resource_notes: string;
  setup_hint: string | null;
  readiness_required: boolean;
};

type ParserCatalogEntry = {
  id: string;
  label: string;
  role: "auto" | "structured" | "fallback" | "ocr_gate" | "ocr_provider";
  supported_as: Array<"structured" | "fallback">;
  notes: string;
  setup_hint: string | null;
  readiness_required: boolean;
};

type RepositoryModelCatalog = {
  repository_id: string;
  embedding_models: EmbeddingModelCatalogEntry[];
  chat_models: ChatModelCatalogEntry[];
  reranker_models: RerankerModelCatalogEntry[];
  parser_choices: ParserCatalogEntry[];
  runtime_detection: {
    checked: boolean;
    provider: "ollama";
    models: string[];
    message: string;
  };
};

type DashboardIndexStatus = "ready" | "missing" | "partial" | "stale";

type DashboardIndexSummary = {
  ready: boolean;
  status: DashboardIndexStatus;
  message: string;
  indexed_chunks: number;
  parsed_chunks: number;
  model: string | null;
};

type DashboardSummary = {
  repository: RepositoryRead;
  counts: {
    documents: number;
    parsed_documents: number;
    chunks: number;
    chat_sessions: number;
    chat_messages: number;
    retrieval_runs: number;
    sandbox_runs: number;
    sandbox_comparisons: number;
    exports: number;
    recreate_events: number;
  };
  full_text: DashboardIndexSummary;
  vector: DashboardIndexSummary;
  settings_readiness: SettingsReadinessResponse;
  active_config: {
    chunking: RepositorySettings["chunking"];
    full_text: RepositorySettings["full_text"];
    vector: RepositorySettings["vector"];
    embedding: RepositorySettings["embedding"];
    reranking: RepositorySettings["reranking"];
    chat_model: string;
    active_chat_prompt_id: string;
    active_chat_prompt_name: string;
  };
  recent_activity: DashboardActivityItem[];
  warnings: string[];
};

type RepositoryAdminInventory = {
  generated_at: string;
  repositories: RepositoryAdminSummary[];
};

type RepositoryAdminSummary = {
  repository: RepositoryRead;
  counts: DashboardSummary["counts"];
  full_text: DashboardIndexSummary;
  vector: DashboardIndexSummary;
  storage_hints: RepositoryAdminStorageHint[];
};

type RepositoryAdminStorageHint = {
  category:
    | "database_records"
    | "app_managed_sources"
    | "external_sources"
    | "full_text_index"
    | "vector_index"
    | "exports"
    | "prompt_sandbox_history"
    | "chat_retrieval_history"
    | "model_caches";
  label: string;
  status: "tracked" | "present" | "not_found" | "preserved" | "out_of_scope";
  detail: string;
};

type RepositoryCleanupAction = "remove" | "preserve" | "skip" | "retry_required";

type RepositoryDeletePreview = {
  repository: RepositoryRead;
  generated_at: string;
  database_counts: {
    repositories: number;
    settings: number;
    documents: number;
    document_versions: number;
    chunks: number;
    chat_sessions: number;
    chat_messages: number;
    retrieval_runs: number;
    retrieval_results: number;
    sandbox_prompts: number;
    sandbox_runs: number;
    sandbox_comparisons: number;
    embedding_runs: number;
    snapshots: number;
  };
  plan: RepositoryCleanupPlanItem[];
  warnings: RepositoryCleanupWarning[];
  destructive: boolean;
};

type RepositoryDeleteResult = {
  repository: RepositoryRead;
  generated_at: string;
  status: "completed" | "completed_with_warnings" | "failed";
  database_counts: RepositoryDeletePreview["database_counts"];
  removed: RepositoryCleanupResultItem[];
  preserved: RepositoryCleanupResultItem[];
  skipped: RepositoryCleanupResultItem[];
  failed: RepositoryCleanupResultItem[];
  warnings: RepositoryCleanupWarning[];
};

type RepositoryClearAllPreview = {
  generated_at: string;
  repositories: RepositoryDeletePreview[];
  database_counts: RepositoryDeletePreview["database_counts"];
  plan: RepositoryCleanupPlanItem[];
  warnings: RepositoryCleanupWarning[];
  confirmation_value: string;
  destructive: boolean;
};

type RepositoryClearAllResult = {
  generated_at: string;
  status: RepositoryDeleteResult["status"];
  repository_results: RepositoryDeleteResult[];
  database_counts: RepositoryDeletePreview["database_counts"];
  removed: RepositoryCleanupResultItem[];
  preserved: RepositoryCleanupResultItem[];
  skipped: RepositoryCleanupResultItem[];
  failed: RepositoryCleanupResultItem[];
  warnings: RepositoryCleanupWarning[];
  default_repository: RepositorySettingsResponse;
};

type RepositoryVectorCleanupRetryResult = {
  generated_at: string;
  status: "completed" | "completed_with_warnings";
  removed: RepositoryCleanupResultItem[];
  failed: RepositoryCleanupResultItem[];
  warnings: RepositoryCleanupWarning[];
};

type RepositoryCleanupPlanItem = {
  category: RepositoryAdminStorageHint["category"];
  label: string;
  action: RepositoryCleanupAction;
  count: number;
  paths: string[];
  detail: string;
};

type RepositoryCleanupResultItem = {
  category: RepositoryAdminStorageHint["category"];
  label: string;
  count: number;
  paths: string[];
  detail: string;
};

type RepositoryCleanupWarning = {
  code: string;
  category: RepositoryAdminStorageHint["category"];
  message: string;
  retryable: boolean;
};

type DashboardActivityItem = {
  kind: "document" | "retrieval" | "chat" | "sandbox" | "export" | "recreate";
  label: string;
  detail: string;
  occurred_at: string;
  route: View;
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

type View =
  | "dashboard"
  | "documents"
  | "source"
  | "search"
  | "sandbox"
  | "chat"
  | "settings"
  | "admin"
  | "export"
  | "recreate";

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

type ReprocessStatus = {
  status: "current" | "stale" | "source_missing" | "unknown";
  stale: boolean;
  reprocess_available: boolean;
  message: string;
  changed_fields: string[];
};

type PageOcrRoute = {
  page: number;
  classification: "born_digital" | "scanned" | "mixed";
  quality_score: number;
  needs_ocr: boolean;
  warnings: string[];
};

type OcrPageResult = {
  page: number;
  text: string;
  confidence: number | null;
  warnings: string[];
  provider: Record<string, unknown>;
  provenance: Record<string, unknown>;
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
type BoostLevel = "off" | "low" | "medium" | "high";
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
    metadata_boost_dimensions?: Record<
      string,
      {
        level: BoostLevel;
        matched: boolean;
        score: number;
        ranking_applied: boolean;
      }
    >;
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

type RetrievalFilters = {
  document_id?: string | null;
  section?: string | null;
  source_type?: string | null;
  document_kind?: string | null;
  tag?: string | null;
  has_table?: boolean | null;
  has_figure?: boolean | null;
  patent_section?: string | null;
};

type MetadataBoostSettings = {
  section: "off" | "low" | "medium" | "high";
  patent_section: "off" | "low" | "medium" | "high";
  document_kind: "off" | "low" | "medium" | "high";
  table_figure: "off" | "low" | "medium" | "high";
};

type RetrievalDefaults = {
  mode: "full_text" | "vector" | "hybrid";
  top_k: number;
  candidate_pool_size?: number | null;
  rrf_constant: number;
  reranker_strategy: RerankerStrategy;
  metadata_boosts: MetadataBoostSettings;
  filters: RetrievalFilters;
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

type ChatRetrievalSettings = RetrievalDefaults;

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

type ChatModelInfo = {
  name: string;
  label: string;
  role: "recommended_default" | "balanced_local" | "larger_local" | "reasoning_experimental";
  required: boolean;
  notes: string | null;
  setup_command: string | null;
  local_resource_notes: string | null;
  context_window_notes: string | null;
  readiness_required: boolean;
};

type ChatModelRegistry = {
  default_model: string;
  models: ChatModelInfo[];
};

type ChatReadinessItem = {
  ready: boolean;
  status:
    | "not_checked"
    | "unavailable_runtime"
    | "not_installed"
    | "ready"
    | "failed"
    | "missing"
    | "partial"
    | "stale";
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
  const [chatRetrievalSettings, setChatRetrievalSettings] = useState<ChatRetrievalSettings>(
    defaultChatRetrievalSettings,
  );
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
  const [chatModelRegistry, setChatModelRegistry] = useState<ChatModelRegistry | null>(null);
  const [modelCatalog, setModelCatalog] = useState<RepositoryModelCatalog | null>(null);
  const [exportIncludeSources, setExportIncludeSources] = useState(true);
  const [exportIncludeSandbox, setExportIncludeSandbox] = useState(false);
  const [exportBusy, setExportBusy] = useState(false);
  const [exportMessage, setExportMessage] = useState("Ready to export");
  const [exportDownloadUrl, setExportDownloadUrl] = useState<string | null>(null);
  const [exportFilename, setExportFilename] = useState<string | null>(null);
  const [exportSummary, setExportSummary] = useState<ExportManifestSummary | null>(null);
  const [dashboardSummary, setDashboardSummary] = useState<DashboardSummary | null>(null);
  const [dashboardMessage, setDashboardMessage] = useState("Loading repository summary");
  const [repositoryLoadState, setRepositoryLoadState] = useState<RepositoryLoadState>({
    repositoryId: null,
    status: "empty",
    message: "No active repository",
  });
  const [adminInventory, setAdminInventory] = useState<RepositoryAdminInventory | null>(null);
  const [adminMessage, setAdminMessage] = useState("Loading local repository inventory");
  const [deletePreview, setDeletePreview] = useState<RepositoryDeletePreview | null>(null);
  const [deleteResult, setDeleteResult] = useState<RepositoryDeleteResult | null>(null);
  const [deleteConfirmation, setDeleteConfirmation] = useState("");
  const [deletePreviewBusy, setDeletePreviewBusy] = useState(false);
  const [deleteBusy, setDeleteBusy] = useState(false);
  const [clearAllPreview, setClearAllPreview] = useState<RepositoryClearAllPreview | null>(null);
  const [clearAllResult, setClearAllResult] = useState<RepositoryClearAllResult | null>(null);
  const [clearAllConfirmation, setClearAllConfirmation] = useState("");
  const [clearAllBusy, setClearAllBusy] = useState(false);
  const [vectorCleanupRetryResult, setVectorCleanupRetryResult] =
    useState<RepositoryVectorCleanupRetryResult | null>(null);
  const [vectorCleanupRetryBusy, setVectorCleanupRetryBusy] = useState(false);
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
  const repositoryLoadCycle = useRef(0);

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
      void loadRepositoryScopedData(repository);
    }
  }, [repository]);

  useEffect(() => {
    if (activeView === "admin") {
      void loadAdminInventory();
    }
  }, [activeView, repository?.id]);

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
      } else {
        setRepositoryLoadState({
          repositoryId: null,
          status: "empty",
          message: "No local repository is active",
        });
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
        setRepositoryLoadState({
          repositoryId: null,
          status: "failed",
          message: "Backend unavailable",
        });
        setMessage("Backend unavailable");
      }
    }
  }

  async function useDefaultRepository() {
    setDashboardMessage("Creating default repository");
    try {
      const response = await fetch(`${API_BASE}/repositories/default`);
      if (!response.ok) {
        throw new Error("default repository unavailable");
      }
      const payload = (await response.json()) as RepositorySettingsResponse;
      setRepositories((current) => mergeRepositories(current, payload.repository));
      setRepositorySettings(payload.settings);
      if (!activeChatSessionId) {
        setChatRetrievalSettings(normalizeChatRetrievalSettings(payload.settings.retrieval));
      }
      activateRepository(payload.repository);
      setMessage("Ready");
    } catch {
      setDashboardMessage("Could not create default repository");
      setMessage("Backend unavailable");
    }
  }

  function activateRepository(nextRepository: RepositoryRead) {
    repositoryLoadCycle.current += 1;
    window.localStorage.setItem("activeRepositoryId", nextRepository.id);
    setRepositoryLoadState({
      repositoryId: nextRepository.id,
      status: "loading",
      message: `Loading ${nextRepository.name}`,
    });
    setRepository(nextRepository);
    setDocuments([]);
    setSelectedDocumentId(null);
    setSelectedChunkId(null);
    setInspection(null);
    setSearchDocumentId("");
    setSearchResults([]);
    setLastRebuild(null);
    setChatModelRegistry(null);
    setModelCatalog(null);
    setDashboardSummary(null);
    setDashboardMessage("Loading repository summary");
    setDeletePreview(null);
    setDeleteResult(null);
    setDeleteConfirmation("");
    setClearAllPreview(null);
    setClearAllResult(null);
    setClearAllConfirmation("");
    setVectorCleanupRetryResult(null);
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

  async function loadRepositoryScopedData(nextRepository: RepositoryRead) {
    const cycle = repositoryLoadCycle.current;
    const results = await Promise.allSettled([
      loadDocuments(nextRepository.id),
      loadRepositorySettings(nextRepository.id),
      loadRepositoryModelCatalog(nextRepository.id),
      loadChatModelRegistry(nextRepository.id),
      loadDashboardSummary(nextRepository.id),
      loadChatSessions(nextRepository.id),
      loadChatReadiness(nextRepository.id),
      loadSandboxPrompts(nextRepository.id),
    ]);
    if (repositoryLoadCycle.current !== cycle) {
      return;
    }
    const failed = results.some((result) => result.status === "rejected" || result.value === false);
    setRepositoryLoadState({
      repositoryId: nextRepository.id,
      status: failed ? "failed" : "loaded",
      message: failed
        ? `Some ${nextRepository.name} data could not load`
        : `${nextRepository.name} loaded`,
    });
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
      return true;
    } catch {
      setMessage("Could not load documents");
      return false;
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
      if (!activeChatSessionId) {
        setChatRetrievalSettings(normalizeChatRetrievalSettings(payload.settings.retrieval));
      }
      setExportIncludeSources(payload.settings.export.include_sources);
      return true;
    } catch {
      setRepositorySettings(null);
      setExportMessage("Could not load export defaults");
      return false;
    }
  }

  async function loadChatModelRegistry(repositoryId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/chat/models`);
      if (!response.ok) {
        throw new Error("chat model registry unavailable");
      }
      const payload = (await response.json()) as ChatModelRegistry;
      setChatModelRegistry(payload);
      setSandboxModel((current) => current || payload.default_model);
      return true;
    } catch {
      setChatModelRegistry(null);
      return false;
    }
  }

  async function loadRepositoryModelCatalog(repositoryId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/settings/model-catalog`);
      if (!response.ok) {
        throw new Error("model catalog unavailable");
      }
      setModelCatalog((await response.json()) as RepositoryModelCatalog);
      return true;
    } catch {
      setModelCatalog(null);
      return false;
    }
  }

  async function loadDashboardSummary(repositoryId: string) {
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/summary`);
      if (!response.ok) {
        throw new Error("summary unavailable");
      }
      setDashboardSummary((await response.json()) as DashboardSummary);
      setDashboardMessage("Repository summary loaded");
      return true;
    } catch {
      setDashboardSummary(null);
      setDashboardMessage("Could not load repository summary");
      return false;
    }
  }

  async function loadAdminInventory() {
    setAdminMessage("Loading local repository inventory");
    try {
      const response = await fetch(`${API_BASE}/repositories/admin/inventory`);
      if (!response.ok) {
        throw new Error("inventory unavailable");
      }
      const payload = (await response.json()) as RepositoryAdminInventory;
      setAdminInventory(payload);
      setRepositories((current) =>
        payload.repositories.reduce(
          (items, item) => mergeRepositories(items, item.repository),
          current,
        ),
      );
      setAdminMessage("Local repository inventory loaded");
    } catch {
      setAdminInventory(null);
      setAdminMessage("Could not load repository administration inventory");
    }
  }

  async function previewRepositoryCleanup(repositoryId: string) {
    setDeletePreviewBusy(true);
    setAdminMessage("Loading repository cleanup preview");
    try {
      const response = await fetch(`${API_BASE}/repositories/${repositoryId}/admin/delete-preview`);
      if (!response.ok) {
        throw new Error("cleanup preview unavailable");
      }
      const payload = (await response.json()) as RepositoryDeletePreview;
      setDeletePreview(payload);
      setDeleteResult(null);
      setVectorCleanupRetryResult(null);
      setDeleteConfirmation("");
      setAdminMessage(`Cleanup preview loaded for ${payload.repository.name}`);
    } catch {
      setDeletePreview(null);
      setDeleteResult(null);
      setAdminMessage("Could not load repository cleanup preview");
    } finally {
      setDeletePreviewBusy(false);
    }
  }

  async function deleteRepositoryFromPreview() {
    if (!deletePreview) {
      return;
    }
    setDeleteBusy(true);
    setAdminMessage(`Deleting ${deletePreview.repository.name}`);
    try {
      const response = await fetch(`${API_BASE}/repositories/${deletePreview.repository.id}/admin/delete`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation_value: deleteConfirmation }),
      });
      if (!response.ok) {
        throw new Error("repository deletion failed");
      }
      const payload = (await response.json()) as RepositoryDeleteResult;
      setDeleteResult(payload);
      setDeletePreview(null);
      setVectorCleanupRetryResult(null);
      setDeleteConfirmation("");
      setRepositories((current) => current.filter((item) => item.id !== payload.repository.id));
      setAdminInventory((current) =>
        current
          ? {
              ...current,
              repositories: current.repositories.filter((item) => item.repository.id !== payload.repository.id),
            }
          : current,
      );
      if (repository?.id === payload.repository.id) {
        window.localStorage.removeItem("activeRepositoryId");
        setRepository(null);
        setDocuments([]);
        setRepositorySettings(null);
        setDashboardSummary(null);
        setRepositoryLoadState({
          repositoryId: null,
          status: "empty",
          message: "No local repository is active",
        });
      }
      void loadAdminInventory();
      setAdminMessage(`Deleted ${payload.repository.name}`);
    } catch {
      setAdminMessage("Repository deletion failed");
    } finally {
      setDeleteBusy(false);
    }
  }

  async function previewClearAllRepositories() {
    setClearAllBusy(true);
    setAdminMessage("Loading clear-all preview");
    try {
      const response = await fetch(`${API_BASE}/repositories/admin/clear-all/preview`);
      if (!response.ok) {
        throw new Error("clear-all preview unavailable");
      }
      const payload = (await response.json()) as RepositoryClearAllPreview;
      setClearAllPreview(payload);
      setClearAllResult(null);
      setVectorCleanupRetryResult(null);
      setClearAllConfirmation("");
      setDeletePreview(null);
      setDeleteResult(null);
      setAdminMessage(`Clear-all preview loaded for ${payload.repositories.length} repositories`);
    } catch {
      setClearAllPreview(null);
      setClearAllResult(null);
      setAdminMessage("Could not load clear-all preview");
    } finally {
      setClearAllBusy(false);
    }
  }

  async function clearAllRepositories() {
    if (!clearAllPreview) {
      return;
    }
    setClearAllBusy(true);
    setAdminMessage("Clearing all local repositories");
    try {
      const response = await fetch(`${API_BASE}/repositories/admin/clear-all`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ confirmation_value: clearAllConfirmation }),
      });
      if (!response.ok) {
        throw new Error("clear all failed");
      }
      const payload = (await response.json()) as RepositoryClearAllResult;
      setClearAllPreview(null);
      setClearAllConfirmation("");
      setVectorCleanupRetryResult(null);
      setRepositories([payload.default_repository.repository]);
      activateRepository(payload.default_repository.repository);
      setClearAllResult(payload);
      setRepositorySettings(payload.default_repository.settings);
      setChatRetrievalSettings(normalizeChatRetrievalSettings(payload.default_repository.settings.retrieval));
      void loadAdminInventory();
      setAdminMessage("Cleared all local repositories and recreated the default repository");
    } catch {
      setAdminMessage("Clear-all cleanup failed");
    } finally {
      setClearAllBusy(false);
    }
  }

  async function retryVectorCleanup(collectionNames: string[]) {
    if (collectionNames.length === 0) {
      return;
    }
    setVectorCleanupRetryBusy(true);
    setAdminMessage("Retrying Qdrant vector cleanup");
    try {
      const response = await fetch(`${API_BASE}/repositories/admin/vector-cleanup/retry`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ collection_names: collectionNames }),
      });
      if (!response.ok) {
        throw new Error("vector cleanup retry failed");
      }
      const payload = (await response.json()) as RepositoryVectorCleanupRetryResult;
      setVectorCleanupRetryResult(payload);
      setAdminMessage(
        payload.failed.length > 0
          ? "Vector cleanup retry still needs attention"
          : "Vector cleanup retry completed",
      );
    } catch {
      setAdminMessage("Vector cleanup retry failed");
    } finally {
      setVectorCleanupRetryBusy(false);
    }
  }

  async function saveRepositorySettings(nextSettings: RepositorySettings) {
    if (!repository) {
      throw new Error("No active repository");
    }
    const response = await fetch(`${API_BASE}/repositories/${repository.id}/settings`, {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: nextSettings }),
    });
    if (!response.ok) {
      throw new Error(await settingsSaveErrorMessage(response));
    }
    const payload = (await response.json()) as RepositorySettingsResponse;
    setRepositorySettings(payload.settings);
    if (!activeChatSessionId) {
      setChatRetrievalSettings(normalizeChatRetrievalSettings(payload.settings.retrieval));
    }
    setExportIncludeSources(payload.settings.export.include_sources);
    void loadDashboardSummary(repository.id);
    return payload.settings;
  }

  async function previewRepositorySettingsImpact(nextSettings: RepositorySettings) {
    if (!repository) {
      throw new Error("No active repository");
    }
    const response = await fetch(`${API_BASE}/repositories/${repository.id}/settings/impact`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ settings: nextSettings }),
    });
    if (!response.ok) {
      throw new Error("Settings impact unavailable");
    }
    return (await response.json()) as SettingsImpactResponse;
  }

  async function checkRepositorySettingsReadiness() {
    if (!repository) {
      throw new Error("No active repository");
    }
    const response = await fetch(`${API_BASE}/repositories/${repository.id}/settings/readiness`, {
      method: "POST",
    });
    if (!response.ok) {
      throw new Error("Settings readiness check failed");
    }
    return (await response.json()) as SettingsReadinessResponse;
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
      return true;
    } catch {
      setChatMessage("Could not load chat sessions");
      return false;
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
      return true;
    } catch {
      setChatReadiness(null);
      if (announce) {
        setChatMessage("Could not check chat readiness");
      }
      return false;
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
      return true;
    } catch {
      setSandboxMessage("Could not load sandbox prompts");
      return false;
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
      void loadDashboardSummary(repository.id);
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
      void loadDashboardSummary(repository.id);
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
      void loadDashboardSummary(repository.id);
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
          retrieval_settings: repositorySettings?.retrieval ?? defaultChatRetrievalSettings(),
        }),
      });
      if (!response.ok) {
        throw new Error("create chat failed");
      }
      const payload = (await response.json()) as ChatSession;
      setChatSessions((current) => [payload, ...current]);
      setActiveChatSessionId(payload.id);
      setChatRetrievalSettings(normalizeChatRetrievalSettings(payload.retrieval_settings));
      void loadDashboardSummary(repository.id);
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
      void loadDashboardSummary(repository.id);
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
      void loadDashboardSummary(repository.id);
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
      void loadDashboardSummary(repository.id);
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
        throw new Error(await apiErrorMessage(response, "rebuild failed"));
      }
      const payload = (await response.json()) as SearchRebuildResponse;
      setChatMessage(`Indexed ${payload.indexed_chunks} ${kind} chunks`);
      await loadChatReadiness(repository.id);
      await loadDashboardSummary(repository.id);
    } catch (error) {
      setChatMessage(`${kind} rebuild failed: ${errorMessage(error)}`);
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
      await loadDashboardSummary(repository.id);
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
      await loadDashboardSummary(repository.id);
      setMessage("Reprocess complete");
    } catch {
      setMessage("Reprocess failed");
    } finally {
      setBusy(false);
    }
  }

  async function runOcrSelected() {
    if (!repository || !selectedDocumentId) {
      return;
    }
    setBusy(true);
    setMessage("Running OCR");
    try {
      const response = await fetch(
        `${API_BASE}/repositories/${repository.id}/documents/${selectedDocumentId}/ocr`,
        { method: "POST" },
      );
      if (!response.ok) {
        throw new Error("OCR failed");
      }
      setInspection((await response.json()) as Inspection);
      await loadDocuments(repository.id);
      await loadDashboardSummary(repository.id);
      setMessage("OCR complete");
    } catch {
      setMessage("OCR failed");
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
      await loadDashboardSummary(repository.id);
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
      await loadDashboardSummary(repository.id);
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
          throw new Error(
            await apiErrorMessage(
              !sparseResponse.ok ? sparseResponse : vectorResponse,
              "hybrid rebuild failed",
            ),
          );
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
          throw new Error(await apiErrorMessage(response, "rebuild failed"));
        }
        const payload = (await response.json()) as SearchRebuildResponse;
        setLastRebuild(payload);
        setSearchMessage(`Indexed ${payload.indexed_chunks} chunks`);
      }
      await loadDashboardSummary(repository.id);
    } catch (error) {
      setSearchMessage(`${searchModeLabel(searchMode)} rebuild failed: ${errorMessage(error)}`);
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
          ...currentSearchRetrievalSettings(),
        }),
      });
      if (!response.ok) {
        throw new Error(await apiErrorMessage(response, "search failed"));
      }
      const payload = (await response.json()) as RetrievalSearchResponse;
      setSearchResults(payload.results.map((result) => ({ ...result, mode: searchMode })));
      void loadDashboardSummary(repository.id);
      setSearchMessage(`${payload.results.length} results · run ${payload.run_id.slice(0, 8)}`);
    } catch (error) {
      setSearchMessage(
        `${searchModeLabel(searchMode)} search failed: ${errorMessage(error)}. Rebuild the index and try again.`,
      );
      setSearchResults([]);
    } finally {
      setSearchBusy(false);
    }
  }

  function currentSearchRetrievalSettings(): RetrievalDefaults {
    return normalizeChatRetrievalSettings({
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
    });
  }

  function copySearchSettingsToChat() {
    setChatRetrievalSettings(currentSearchRetrievalSettings());
    setSearchMessage("Copied Search Lab retrieval settings to the Chat Workspace panel");
  }

  async function promoteSearchSettingsToRepositoryDefaults() {
    if (!repositorySettings) {
      setSearchMessage("Repository settings unavailable");
      return;
    }
    const nextSettings = cloneSettings(repositorySettings);
    if (!nextSettings) {
      setSearchMessage("Repository settings unavailable");
      return;
    }
    nextSettings.retrieval = currentSearchRetrievalSettings();
    try {
      const saved = await saveRepositorySettings(nextSettings);
      setRepositorySettings(saved);
      setSearchMessage("Promoted Search Lab retrieval settings to repository defaults");
    } catch (error) {
      setSearchMessage(`Could not promote retrieval defaults: ${errorMessage(error)}`);
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
      void loadDashboardSummary(repository.id);
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
    window.location.hash = hashForView(view);
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
    activeView === "dashboard"
      ? "Repository Dashboard"
      : activeView === "search"
      ? "Search Lab"
      : activeView === "source"
        ? "Source Viewer"
        : activeView === "chat"
          ? "Chat Workspace"
          : activeView === "sandbox"
            ? "Prompt Sandbox"
            : activeView === "settings"
              ? "Settings / Models"
              : activeView === "admin"
                ? "Repository Administration"
            : activeView === "export"
              ? "Export Center"
              : activeView === "recreate"
                ? "Recreate Repository"
          : "Document Manager";
  const subtitle =
    repositoryLoadState.status === "loading"
      ? repositoryLoadState.message
      : repositoryLoadState.status === "failed"
        ? repositoryLoadState.message
        :
    activeView === "dashboard"
      ? `${repository?.name ?? "Default Repository"} · repository overview`
      : activeView === "search"
      ? "Inspect full-text retrieval with BM25 scores and citation provenance"
      : activeView === "sandbox"
        ? `${repository?.name ?? "Default Repository"} · ${sandboxMessage}`
      : activeView === "export"
        ? `${repository?.name ?? "Default Repository"} · ${exportMessage}`
      : activeView === "settings"
        ? `${repository?.name ?? "Default Repository"} · repository defaults`
      : activeView === "admin"
        ? `${adminInventory?.repositories.length ?? repositories.length} local repositories · ${adminMessage}`
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
            <a
              className={activeView === "dashboard" ? "active" : ""}
              href="#home"
              onClick={() => navigateTo("dashboard")}
            >
              Home
            </a>
            <span className="nav-label">Workspace</span>
            <a
              className={activeView === "dashboard" ? "active" : ""}
              href="#repository-dashboard"
              onClick={() => navigateTo("dashboard")}
            >
              Repository Dashboard
            </a>
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
            <a
              className={activeView === "settings" ? "active" : ""}
              href="#settings-models"
              onClick={() => navigateTo("settings")}
            >
              Settings / Models
            </a>
            <a
              className={activeView === "admin" ? "active" : ""}
              href="#repository-administration"
              onClick={() => navigateTo("admin")}
            >
              Repository Administration
            </a>
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
              <span className={`badge repository-load-${repositoryLoadState.status}`}>
                <span className="dot" />
                {repositoryLoadState.status === "loading"
                  ? "Loading"
                  : repositoryLoadState.status === "loaded"
                    ? "Loaded"
                    : repositoryLoadState.status === "failed"
                      ? "Load failed"
                      : "No repository"}
              </span>
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
            {activeView === "dashboard" ? (
              <RepositoryDashboard
                repository={repository}
                repositories={repositories}
                documents={documents}
                totalChunks={totalChunks}
                chatSessions={chatSessions}
                settings={repositorySettings}
                summary={dashboardSummary}
                message={dashboardMessage}
                loadState={repositoryLoadState}
                onSelectRepository={activateRepository}
                onUseDefaultRepository={() => void useDefaultRepository()}
                onNavigate={navigateTo}
              />
            ) : activeView === "admin" ? (
              <RepositoryAdministration
                inventory={adminInventory}
                activeRepositoryId={repository?.id ?? null}
                preview={deletePreview}
                result={deleteResult}
                clearAllPreview={clearAllPreview}
                clearAllResult={clearAllResult}
                vectorCleanupRetryResult={vectorCleanupRetryResult}
                previewBusy={deletePreviewBusy}
                deleteBusy={deleteBusy}
                confirmationValue={deleteConfirmation}
                clearAllBusy={clearAllBusy}
                vectorCleanupRetryBusy={vectorCleanupRetryBusy}
                clearAllConfirmationValue={clearAllConfirmation}
                message={adminMessage}
                onRefresh={() => void loadAdminInventory()}
                onPreviewCleanup={(repositoryId) => void previewRepositoryCleanup(repositoryId)}
                onConfirmationChange={setDeleteConfirmation}
                onDeleteRepository={() => void deleteRepositoryFromPreview()}
                onPreviewClearAll={() => void previewClearAllRepositories()}
                onClearAllConfirmationChange={setClearAllConfirmation}
                onClearAllRepositories={() => void clearAllRepositories()}
                onRetryVectorCleanup={(collectionNames) => void retryVectorCleanup(collectionNames)}
                onSelectRepository={activateRepository}
                onNavigate={navigateTo}
              />
            ) : activeView === "search" ? (
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
                onCopyToChat={copySearchSettingsToChat}
                onPromoteToDefaults={() => void promoteSearchSettingsToRepositoryDefaults()}
                onOpenResult={openSearchResult}
              />
            ) : activeView === "chat" ? (
              <ChatWorkspace
                settings={repositorySettings}
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
                chatModelRegistry={chatModelRegistry}
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
                defaultIncludeSources={repositorySettings?.export.include_sources ?? true}
                defaultIncludeIndexes={repositorySettings?.export.include_indexes ?? false}
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
            ) : activeView === "settings" ? (
              <SettingsModels
                repository={repository}
                settings={repositorySettings}
                chatModelRegistry={chatModelRegistry}
                modelCatalog={modelCatalog}
                dashboardSummary={dashboardSummary}
                onNavigate={navigateTo}
                onSave={saveRepositorySettings}
                onAnalyzeImpact={previewRepositorySettingsImpact}
                onCheckReadiness={checkRepositorySettingsReadiness}
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
                                    {document.current_version && (
                                      <div className="muted table-sub">
                                        {reprocessStatusLabel(document.current_version)}
                                      </div>
                                    )}
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
                        onRunOcr={() => void runOcrSelected()}
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
                            page {image.page} · {ocrPageLabel(inspection.version, image.page)}
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
                        version={inspection.version}
                      />
                    )}
                    {inspection.version.source_type === "pdf" && selectedPageImages.length > 0 && (
                      <OcrPageTextPanel
                        version={inspection.version}
                        pages={selectedPageImages.map((image) => image.page)}
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
                                {isOcrChunk(chunk) ? " · OCR text" : ""}
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
                        <dd>{parserDisplayLabel(inspection.version)}</dd>
                        <dt>parser version</dt>
                        <dd>{inspection.version.parser_version}</dd>
                        <dt>reprocess</dt>
                        <dd>{reprocessStatusLabel(inspection.version)}</dd>
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
                        <dd>{parserDisplayLabel(inspection.version)}</dd>
                        <dt>parser version</dt>
                        <dd>{inspection.version.parser_version}</dd>
                        <dt>reprocess</dt>
                        <dd>{reprocessStatusLabel(inspection.version)}</dd>
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

function RepositoryDashboard({
  repository,
  repositories,
  documents,
  totalChunks,
  chatSessions,
  settings,
  summary,
  message,
  loadState,
  onSelectRepository,
  onUseDefaultRepository,
  onNavigate,
}: {
  repository: RepositoryResponse["repository"] | null;
  repositories: RepositoryRead[];
  documents: DocumentSummary[];
  totalChunks: number;
  chatSessions: ChatSession[];
  settings: RepositorySettings | null;
  summary: DashboardSummary | null;
  message: string;
  loadState: RepositoryLoadState;
  onSelectRepository: (repository: RepositoryRead) => void;
  onUseDefaultRepository: () => void;
  onNavigate: (view: View) => void;
}) {
  if (!repository) {
    return (
      <div className="dashboard-layout">
        <section className="card dashboard-empty">
          <div>
            <div className="eyebrow">Repository dashboard</div>
            <h2>No local repository is active</h2>
            <p>
              Create or use the default local repository to start fresh, or restore a repository
              from a portable export bundle.
            </p>
          </div>
          <div className="dashboard-actions">
            <button className="btn btn-primary" type="button" onClick={onUseDefaultRepository}>
              Use default repository
            </button>
            <button className="btn" type="button" onClick={() => onNavigate("recreate")}>
              Open Recreate Repository
            </button>
          </div>
        </section>
      </div>
    );
  }

  const fallbackParsedDocuments = documents.filter((document) => document.current_version?.status === "parsed").length;
  const counts = summary?.counts;
  const activeConfig = summary?.active_config;
  const activePrompt = settings?.prompt.library.find((prompt) => prompt.id === settings.prompt.active_chat_prompt_id);
  const configRows = dashboardConfigRows(summary, settings);
  const warnings = summary?.warnings ?? [];
  const recentActivity = summary?.recent_activity ?? [];
  const loadingCurrentRepository =
    loadState.status === "loading" && loadState.repositoryId === repository.id;
  const failedCurrentRepository =
    loadState.status === "failed" && loadState.repositoryId === repository.id;
  const dashboardStatusMessage = loadingCurrentRepository
    ? "Loading repository state. Previous repository data has been cleared."
    : failedCurrentRepository
      ? loadState.message
      : message;

  return (
    <div className="dashboard-layout">
      <section className="card dashboard-overview">
        <div className="row row-between">
          <div>
            <div className="eyebrow">Repository dashboard</div>
            <h2>{repository?.name ?? "No active repository"}</h2>
          </div>
          <span
            className={`badge ${
              failedCurrentRepository ? "badge-danger" : loadingCurrentRepository ? "badge-warn" : "badge-ok"
            }`}
          >
            <span className="dot" />
            {failedCurrentRepository
              ? "Load failed"
              : loadingCurrentRepository
                ? "Loading repository"
                : "Active repository"}
          </span>
        </div>
        <p className="hint">{dashboardStatusMessage}</p>
        {loadingCurrentRepository && (
          <div className="dashboard-loading" role="status">
            Refreshing counts, settings, documents, chat sessions, and model catalog.
          </div>
        )}
        {repositories.length > 1 && (
          <label className="dashboard-repository-picker" htmlFor="dashboard-repository">
            <span>Repository</span>
            <select
              id="dashboard-repository"
              value={repository.id}
              onChange={(event) => {
                const selectedRepository = repositories.find((item) => item.id === event.target.value);
                if (selectedRepository) {
                  onSelectRepository(selectedRepository);
                }
              }}
            >
              {repositories.map((item) => (
                <option value={item.id} key={item.id}>
                  {item.name}
                </option>
              ))}
            </select>
          </label>
        )}
        <dl className="kv dashboard-kv">
          <dt>repository id</dt>
          <dd>{repository?.id ?? "unavailable"}</dd>
          <dt>root path</dt>
          <dd>{repository?.root_path ?? "local default"}</dd>
          <dt>created</dt>
          <dd>{repository?.created_at ? formatDate(repository.created_at) : "unavailable"}</dd>
          <dt>updated</dt>
          <dd>{repository?.updated_at ? formatDate(repository.updated_at) : "unavailable"}</dd>
        </dl>
      </section>

      <div className="dashboard-grid">
        <DashboardMetric
          label="Documents"
          value={counts?.documents ?? documents.length}
          detail={`${counts?.parsed_documents ?? fallbackParsedDocuments} parsed`}
        />
        <DashboardMetric
          label="Chunks"
          value={counts?.chunks ?? totalChunks}
          detail="parsed repository context"
        />
        <DashboardMetric
          label="Chat"
          value={counts?.chat_sessions ?? chatSessions.length}
          detail={`${counts?.chat_messages ?? 0} messages`}
        />
        <DashboardMetric
          label="Retrieval"
          value={counts?.retrieval_runs ?? 0}
          detail="saved search runs"
        />
        <DashboardMetric
          label="Sandbox"
          value={counts?.sandbox_runs ?? 0}
          detail={`${counts?.sandbox_comparisons ?? 0} comparisons`}
        />
        <DashboardMetric label="Exports" value={counts?.exports ?? 0} detail="portable bundles" />
        <DashboardMetric label="Recreate" value={counts?.recreate_events ?? 0} detail="restore events" />
        <DashboardMetric
          label="Chat default"
          value={activeConfig?.chat_model ?? settings?.model.ollama_chat_model ?? "unavailable"}
          detail={activeConfig?.active_chat_prompt_name ?? activePrompt?.name ?? "active prompt"}
        />
      </div>

      <div className="dashboard-status-grid">
        <DashboardIndexCard label="Full-text" item={summary?.full_text ?? null} onNavigate={onNavigate} />
        <DashboardIndexCard label="Vector" item={summary?.vector ?? null} onNavigate={onNavigate} />
      </div>

      <section className="card dashboard-status" aria-label="Dashboard quick actions">
        <div>
          <div className="eyebrow">Quick actions</div>
          <h2>Open workflow</h2>
        </div>
        <div className="dashboard-quick-actions">
          {dashboardQuickActions().map((action) => (
            <button className="btn btn-sm" type="button" onClick={() => onNavigate(action.view)} key={action.view}>
              {action.label}
            </button>
          ))}
        </div>
      </section>

      <section className="card dashboard-status" aria-label="Model and service readiness">
        <div>
          <div className="eyebrow">Runtime readiness</div>
          <h2>Models and local services</h2>
        </div>
        <div className="settings-readiness-grid dashboard-readiness-grid">
          {dashboardReadinessItems(summary, settings).map((item) => (
            <ReadinessCard item={item} onNavigate={onNavigate} key={item.target} />
          ))}
        </div>
      </section>

      <section className="card dashboard-status" aria-label="Active configuration">
        <div>
          <div className="eyebrow">Active configuration</div>
          <h2>Saved defaults</h2>
        </div>
        <dl className="kv dashboard-config">
          {configRows.map((row) => (
            <React.Fragment key={row.label}>
              <dt>{row.label}</dt>
              <dd>{row.value}</dd>
            </React.Fragment>
          ))}
        </dl>
      </section>

      <section className="card dashboard-status" aria-label="Recent activity">
        <div>
          <div className="eyebrow">Recent activity</div>
          <h2>{recentActivity.length > 0 ? "Latest repository events" : "No recent activity"}</h2>
        </div>
        {recentActivity.length > 0 ? (
          <div className="dashboard-activity-list">
            {recentActivity.map((item) => (
              <button
                className="dashboard-activity"
                type="button"
                onClick={() => onNavigate(item.route)}
                key={`${item.kind}-${item.occurred_at}-${item.label}`}
              >
                <span>{dashboardActivityKindLabel(item.kind)}</span>
                <strong>{item.label}</strong>
                <small>
                  {item.detail} · {formatDate(item.occurred_at)}
                </small>
              </button>
            ))}
          </div>
        ) : (
          <p className="hint">Upload documents, search, chat, run sandbox checks, export, or recreate to populate activity.</p>
        )}
      </section>

      <section className="card dashboard-status" aria-label="Dashboard warnings">
        <div>
          <div className="eyebrow">Warnings</div>
          <h2>{warnings.length > 0 ? `${warnings.length} items need attention` : "No blocking warnings"}</h2>
        </div>
        {warnings.length > 0 ? (
          <div className="dashboard-warning-list">
            {warnings.map((warning, index) => (
              <article className="dashboard-warning" key={`${warning}-${index}`}>
                <p>{warning}</p>
                <div className="dashboard-actions">
                  {dashboardWarningLinks(warning).map((link) => (
                    <button className="btn btn-sm" type="button" onClick={() => onNavigate(link.view)} key={link.view}>
                      {link.label}
                    </button>
                  ))}
                </div>
              </article>
            ))}
          </div>
        ) : (
          <p className="hint">Repository indexes and runtime checks have no dashboard warnings.</p>
        )}
      </section>
    </div>
  );
}

function RepositoryAdministration({
  inventory,
  activeRepositoryId,
  preview,
  result,
  clearAllPreview,
  clearAllResult,
  vectorCleanupRetryResult,
  previewBusy,
  deleteBusy,
  confirmationValue,
  clearAllBusy,
  vectorCleanupRetryBusy,
  clearAllConfirmationValue,
  message,
  onRefresh,
  onPreviewCleanup,
  onConfirmationChange,
  onDeleteRepository,
  onPreviewClearAll,
  onClearAllConfirmationChange,
  onClearAllRepositories,
  onRetryVectorCleanup,
  onSelectRepository,
  onNavigate,
}: {
  inventory: RepositoryAdminInventory | null;
  activeRepositoryId: string | null;
  preview: RepositoryDeletePreview | null;
  result: RepositoryDeleteResult | null;
  clearAllPreview: RepositoryClearAllPreview | null;
  clearAllResult: RepositoryClearAllResult | null;
  vectorCleanupRetryResult: RepositoryVectorCleanupRetryResult | null;
  previewBusy: boolean;
  deleteBusy: boolean;
  confirmationValue: string;
  clearAllBusy: boolean;
  vectorCleanupRetryBusy: boolean;
  clearAllConfirmationValue: string;
  message: string;
  onRefresh: () => void;
  onPreviewCleanup: (repositoryId: string) => void;
  onConfirmationChange: (value: string) => void;
  onDeleteRepository: () => void;
  onPreviewClearAll: () => void;
  onClearAllConfirmationChange: (value: string) => void;
  onClearAllRepositories: () => void;
  onRetryVectorCleanup: (collectionNames: string[]) => void;
  onSelectRepository: (repository: RepositoryRead) => void;
  onNavigate: (view: View) => void;
}) {
  const repositories = inventory?.repositories ?? [];
  const totals = repositories.reduce(
    (sum, item) => ({
      documents: sum.documents + item.counts.documents,
      chunks: sum.chunks + item.counts.chunks,
      chat: sum.chat + item.counts.chat_sessions,
      retrieval: sum.retrieval + item.counts.retrieval_runs,
      sandbox: sum.sandbox + item.counts.sandbox_runs,
    }),
    { documents: 0, chunks: 0, chat: 0, retrieval: 0, sandbox: 0 },
  );

  return (
    <div className="admin-layout">
      <section className="card admin-overview">
        <div className="row row-between">
          <div>
            <div className="eyebrow">Repository administration</div>
            <h2>Local repository inventory</h2>
          </div>
          <button className="btn btn-sm" type="button" onClick={onRefresh}>
            Refresh
          </button>
        </div>
        <p className="hint">
          {message}. This inventory is local to this machine and does not manage remote or cloud
          repositories.
        </p>
        <div className="dashboard-grid admin-totals">
          <DashboardMetric label="Repositories" value={repositories.length} detail="local only" />
          <DashboardMetric label="Documents" value={totals.documents} detail="tracked records" />
          <DashboardMetric label="Chunks" value={totals.chunks} detail="parsed context" />
          <DashboardMetric label="Chat" value={totals.chat} detail="saved sessions" />
          <DashboardMetric label="Retrieval" value={totals.retrieval} detail="saved runs" />
          <DashboardMetric label="Sandbox" value={totals.sandbox} detail="saved runs" />
        </div>
      </section>

      {repositories.length === 0 ? (
        <section className="card dashboard-empty">
          <div>
            <div className="eyebrow">No repositories</div>
            <h2>No local repositories were found</h2>
            <p>Create or use the default repository, or recreate from a portable export bundle.</p>
          </div>
          <div className="dashboard-actions">
            <button className="btn btn-primary" type="button" onClick={() => onNavigate("dashboard")}>
              Open Repository Dashboard
            </button>
            <button className="btn" type="button" onClick={() => onNavigate("recreate")}>
              Open Recreate Repository
            </button>
          </div>
        </section>
      ) : (
        <section className="card admin-table-card" aria-label="Repository administration list">
          <div className="table-wrap">
            <table>
              <thead>
                <tr>
                  <th>Repository</th>
                  <th>Created</th>
                  <th>Updated</th>
                  <th>Counts</th>
                  <th>Indexes</th>
                  <th>Storage hints</th>
                  <th>Action</th>
                </tr>
              </thead>
              <tbody>
                {repositories.map((item) => (
                  <tr key={item.repository.id}>
                    <td>
                      <span className="name">{item.repository.name}</span>
                      <span className="table-sub">{item.repository.root_path ?? "local default"}</span>
                      {item.repository.id === activeRepositoryId && (
                        <span className="badge badge-ok admin-active-badge">
                          <span className="dot" />
                          Active
                        </span>
                      )}
                    </td>
                    <td>{item.repository.created_at ? formatDate(item.repository.created_at) : "unavailable"}</td>
                    <td>{item.repository.updated_at ? formatDate(item.repository.updated_at) : "unavailable"}</td>
                    <td>
                      <span className="table-sub">
                        {item.counts.documents} docs · {item.counts.chunks} chunks
                      </span>
                      <span className="table-sub">
                        {item.counts.chat_sessions} chats · {item.counts.retrieval_runs} retrieval
                      </span>
                      <span className="table-sub">
                        {item.counts.sandbox_runs} sandbox · {item.counts.sandbox_comparisons} comparisons
                      </span>
                    </td>
                    <td>
                      <AdminIndexPill label="Full-text" item={item.full_text} />
                      <AdminIndexPill label="Vector" item={item.vector} />
                    </td>
                    <td>
                      <div className="admin-hints">
                        {item.storage_hints.slice(0, 5).map((hint) => (
                          <span className="admin-hint" key={hint.category} title={hint.detail}>
                            {hint.label}: {adminStorageStatusLabel(hint.status)}
                          </span>
                        ))}
                      </div>
                    </td>
                    <td>
                      <button
                        className="btn btn-sm"
                        type="button"
                        onClick={() => onPreviewCleanup(item.repository.id)}
                        disabled={previewBusy}
                      >
                        Preview cleanup
                      </button>
                      <button
                        className="btn btn-sm"
                        type="button"
                        onClick={() => {
                          onSelectRepository(item.repository);
                          onNavigate("dashboard");
                        }}
                      >
                        Open
                      </button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>
      )}

      <section className="card admin-preview-panel" aria-label="Clear all local repositories">
        <div className="row row-between">
          <div>
            <div className="eyebrow">Clear all</div>
            <h2>All local repositories</h2>
          </div>
          <button
            className="btn btn-ghost danger-action"
            type="button"
            onClick={onPreviewClearAll}
            disabled={clearAllBusy || repositories.length === 0}
          >
            Preview clear all
          </button>
        </div>
        <p className="hint">
          Preview every local repository before clearing local records and app-managed artifacts.
          External source files and model caches are preserved.
        </p>
      </section>

      {preview && (
        <RepositoryCleanupPreviewPanel
          preview={preview}
          confirmationValue={confirmationValue}
          deleteBusy={deleteBusy}
          onConfirmationChange={onConfirmationChange}
          onDeleteRepository={onDeleteRepository}
        />
      )}
      {result && (
        <RepositoryCleanupResultPanel
          result={result}
          retryResult={vectorCleanupRetryResult}
          retryBusy={vectorCleanupRetryBusy}
          onRetryVectorCleanup={onRetryVectorCleanup}
        />
      )}
      {clearAllPreview && (
        <RepositoryClearAllPreviewPanel
          preview={clearAllPreview}
          confirmationValue={clearAllConfirmationValue}
          busy={clearAllBusy}
          onConfirmationChange={onClearAllConfirmationChange}
          onClearAllRepositories={onClearAllRepositories}
        />
      )}
      {clearAllResult && (
        <RepositoryClearAllResultPanel
          result={clearAllResult}
          retryResult={vectorCleanupRetryResult}
          retryBusy={vectorCleanupRetryBusy}
          onNavigate={onNavigate}
          onRetryVectorCleanup={onRetryVectorCleanup}
        />
      )}
    </div>
  );
}

function RepositoryCleanupPreviewPanel({
  preview,
  confirmationValue,
  deleteBusy,
  onConfirmationChange,
  onDeleteRepository,
}: {
  preview: RepositoryDeletePreview;
  confirmationValue: string;
  deleteBusy: boolean;
  onConfirmationChange: (value: string) => void;
  onDeleteRepository: () => void;
}) {
  const databaseRows = Object.entries(preview.database_counts).filter(([, value]) => value > 0);
  const confirmationMatches = confirmationValue === preview.repository.name;
  return (
    <section className="card admin-preview-panel" aria-label="Repository cleanup preview">
      <div>
        <div className="eyebrow">Cleanup preview</div>
        <h2>{preview.repository.name}</h2>
      </div>
      <p className="hint">
        Preview generated {formatDate(preview.generated_at)}. No records, files, indexes, or model
        caches are changed by this preview.
      </p>
      <div className="admin-preview-grid">
        <section>
          <h3>Database records</h3>
          <dl className="kv dashboard-kv">
            {databaseRows.map(([label, value]) => (
              <React.Fragment key={label}>
                <dt>{label.replace(/_/g, " ")}</dt>
                <dd>{value}</dd>
              </React.Fragment>
            ))}
          </dl>
        </section>
        <section>
          <h3>Warnings</h3>
          {preview.warnings.length > 0 ? (
            <div className="admin-warning-list">
              {preview.warnings.map((warning) => (
                <article className="dashboard-warning" key={warning.code}>
                  <strong>{adminCleanupCategoryLabel(warning.category)}</strong>
                  <p>{warning.message}</p>
                  {warning.retryable && <small>Retry available after the local service is reachable.</small>}
                </article>
              ))}
            </div>
          ) : (
            <p className="hint">No cleanup warnings were reported.</p>
          )}
        </section>
      </div>
      <div className="admin-plan-list">
        {preview.plan.map((item) => (
          <article className={`admin-plan-item admin-plan-${item.action}`} key={item.category}>
            <div className="row row-between">
              <div>
                <span>{adminCleanupActionLabel(item.action)}</span>
                <strong>{item.label}</strong>
              </div>
              <b>{item.count}</b>
            </div>
            <p>{item.detail}</p>
            {item.paths.length > 0 && (
              <ul>
                {item.paths.slice(0, 4).map((path) => (
                  <li key={path}>{path}</li>
                ))}
              </ul>
            )}
          </article>
        ))}
      </div>
      <div className="admin-confirm-delete">
        <label htmlFor="delete-repository-confirmation">
          <span>Type repository name to confirm</span>
          <input
            id="delete-repository-confirmation"
            type="text"
            value={confirmationValue}
            onChange={(event) => onConfirmationChange(event.target.value)}
            placeholder={preview.repository.name}
          />
        </label>
        <button
          className="btn btn-ghost danger-action"
          type="button"
          onClick={onDeleteRepository}
          disabled={!confirmationMatches || deleteBusy}
        >
          Delete repository
        </button>
      </div>
    </section>
  );
}

function RepositoryCleanupResultPanel({
  result,
  retryResult,
  retryBusy,
  onRetryVectorCleanup,
}: {
  result: RepositoryDeleteResult;
  retryResult: RepositoryVectorCleanupRetryResult | null;
  retryBusy: boolean;
  onRetryVectorCleanup: (collectionNames: string[]) => void;
}) {
  const retryCollectionNames = vectorCleanupRetryCollectionNames(result.failed);
  return (
    <section className="card admin-preview-panel" aria-label="Repository cleanup result">
      <div>
        <div className="eyebrow">Cleanup result</div>
        <h2>{result.repository.name}</h2>
      </div>
      <p className="hint">
        Completed {formatDate(result.generated_at)} with status {repositoryDeleteStatusLabel(result.status)}.
      </p>
      <div className="admin-result-grid">
        <RepositoryCleanupResultGroup title="Removed" items={result.removed} />
        <RepositoryCleanupResultGroup title="Preserved" items={result.preserved} />
        <RepositoryCleanupResultGroup title="Skipped" items={result.skipped} />
        <RepositoryCleanupResultGroup title="Failed" items={result.failed} />
      </div>
      {result.warnings.length > 0 && (
        <div className="admin-warning-list">
          {result.warnings.map((warning) => (
            <article className="dashboard-warning" key={`${warning.code}-${warning.category}`}>
              <strong>{warning.code.replace(/_/g, " ")}</strong>
              <p>{warning.message}</p>
              {warning.retryable && <small>Retry cleanup after the local service is reachable.</small>}
            </article>
          ))}
        </div>
      )}
      {retryCollectionNames.length > 0 && (
        <VectorCleanupRetryPanel
          collectionNames={retryCollectionNames}
          retryResult={retryResult}
          busy={retryBusy}
          onRetryVectorCleanup={onRetryVectorCleanup}
        />
      )}
    </section>
  );
}

function RepositoryClearAllPreviewPanel({
  preview,
  confirmationValue,
  busy,
  onConfirmationChange,
  onClearAllRepositories,
}: {
  preview: RepositoryClearAllPreview;
  confirmationValue: string;
  busy: boolean;
  onConfirmationChange: (value: string) => void;
  onClearAllRepositories: () => void;
}) {
  const databaseRows = Object.entries(preview.database_counts).filter(([, value]) => value > 0);
  const confirmationMatches = confirmationValue === preview.confirmation_value;
  return (
    <section className="card admin-preview-panel" aria-label="Clear-all cleanup preview">
      <div>
        <div className="eyebrow">Clear-all preview</div>
        <h2>{preview.repositories.length} local repositories</h2>
      </div>
      <p className="hint">
        Preview generated {formatDate(preview.generated_at)}. Clearing all removes local
        repository records and app-managed artifacts, then recreates the default repository.
      </p>
      <div className="admin-preview-grid">
        <section>
          <h3>Aggregate database records</h3>
          <dl className="kv dashboard-kv">
            {databaseRows.map(([label, value]) => (
              <React.Fragment key={label}>
                <dt>{label.replace(/_/g, " ")}</dt>
                <dd>{value}</dd>
              </React.Fragment>
            ))}
          </dl>
        </section>
        <section>
          <h3>Repositories</h3>
          <div className="admin-plan-list">
            {preview.repositories.map((item) => (
              <article className="admin-result-item" key={item.repository.id}>
                <strong>{item.repository.name}</strong>
                <p>
                  {item.database_counts.documents} documents · {item.database_counts.chunks} chunks
                </p>
              </article>
            ))}
          </div>
        </section>
      </div>
      <div className="admin-plan-list">
        {preview.plan.map((item) => (
          <article className={`admin-plan-item admin-plan-${item.action}`} key={item.category}>
            <div className="row row-between">
              <div>
                <span>{adminCleanupActionLabel(item.action)}</span>
                <strong>{item.label}</strong>
              </div>
              <b>{item.count}</b>
            </div>
            <p>{item.detail}</p>
          </article>
        ))}
      </div>
      {preview.warnings.length > 0 && (
        <div className="admin-warning-list">
          {preview.warnings.map((warning) => (
            <article className="dashboard-warning" key={`${warning.code}-${warning.message}`}>
              <strong>{warning.code.replace(/_/g, " ")}</strong>
              <p>{warning.message}</p>
              {warning.retryable && <small>Retry cleanup after the local service is reachable.</small>}
            </article>
          ))}
        </div>
      )}
      <div className="admin-confirm-delete">
        <label htmlFor="clear-all-confirmation">
          <span>Type confirmation phrase</span>
          <input
            id="clear-all-confirmation"
            type="text"
            value={confirmationValue}
            onChange={(event) => onConfirmationChange(event.target.value)}
            placeholder={preview.confirmation_value}
          />
        </label>
        <button
          className="btn btn-ghost danger-action"
          type="button"
          onClick={onClearAllRepositories}
          disabled={!confirmationMatches || busy}
        >
          Clear all local repositories
        </button>
      </div>
    </section>
  );
}

function RepositoryClearAllResultPanel({
  result,
  retryResult,
  retryBusy,
  onNavigate,
  onRetryVectorCleanup,
}: {
  result: RepositoryClearAllResult;
  retryResult: RepositoryVectorCleanupRetryResult | null;
  retryBusy: boolean;
  onNavigate: (view: View) => void;
  onRetryVectorCleanup: (collectionNames: string[]) => void;
}) {
  const retryCollectionNames = vectorCleanupRetryCollectionNames(result.failed);
  return (
    <section className="card admin-preview-panel" aria-label="Clear-all cleanup result">
      <div>
        <div className="eyebrow">Clear-all result</div>
        <h2>{repositoryDeleteStatusLabel(result.status)}</h2>
      </div>
      <p className="hint">
        Cleared {result.repository_results.length} repositories and recreated{" "}
        {result.default_repository.repository.name}.
      </p>
      <div className="admin-result-grid">
        <RepositoryCleanupResultGroup title="Removed" items={result.removed} />
        <RepositoryCleanupResultGroup title="Preserved" items={result.preserved} />
        <RepositoryCleanupResultGroup title="Skipped" items={result.skipped} />
        <RepositoryCleanupResultGroup title="Failed" items={result.failed} />
      </div>
      {retryCollectionNames.length > 0 && (
        <VectorCleanupRetryPanel
          collectionNames={retryCollectionNames}
          retryResult={retryResult}
          busy={retryBusy}
          onRetryVectorCleanup={onRetryVectorCleanup}
        />
      )}
      <div className="dashboard-actions">
        <button className="btn btn-primary" type="button" onClick={() => onNavigate("dashboard")}>
          Open Repository Dashboard
        </button>
        <button className="btn" type="button" onClick={() => onNavigate("recreate")}>
          Open Recreate Repository
        </button>
      </div>
    </section>
  );
}

function VectorCleanupRetryPanel({
  collectionNames,
  retryResult,
  busy,
  onRetryVectorCleanup,
}: {
  collectionNames: string[];
  retryResult: RepositoryVectorCleanupRetryResult | null;
  busy: boolean;
  onRetryVectorCleanup: (collectionNames: string[]) => void;
}) {
  return (
    <section className="admin-preview-panel" aria-label="Vector cleanup retry guidance">
      <div>
        <h3>Retry Qdrant cleanup</h3>
        <p className="hint">
          Start the configured Qdrant service, then retry the leftover vector collection cleanup.
          Repository records are already removed, so this does not require deleting the repository again.
        </p>
      </div>
      <ul>
        {collectionNames.map((collectionName) => (
          <li key={collectionName}>{collectionName}</li>
        ))}
      </ul>
      <button
        className="btn btn-sm"
        type="button"
        onClick={() => onRetryVectorCleanup(collectionNames)}
        disabled={busy}
      >
        Retry vector cleanup
      </button>
      {retryResult && (
        <div className="admin-result-grid">
          <RepositoryCleanupResultGroup title="Retry removed" items={retryResult.removed} />
          <RepositoryCleanupResultGroup title="Retry failed" items={retryResult.failed} />
        </div>
      )}
    </section>
  );
}

function RepositoryCleanupResultGroup({
  title,
  items,
}: {
  title: string;
  items: RepositoryCleanupResultItem[];
}) {
  return (
    <section>
      <h3>{title}</h3>
      {items.length > 0 ? (
        <div className="admin-plan-list">
          {items.map((item) => (
            <article className="admin-result-item" key={`${title}-${item.category}`}>
              <div className="row row-between">
                <strong>{item.label}</strong>
                <b>{item.count}</b>
              </div>
              <p>{item.detail}</p>
            </article>
          ))}
        </div>
      ) : (
        <p className="hint">No items.</p>
      )}
    </section>
  );
}

function vectorCleanupRetryCollectionNames(items: RepositoryCleanupResultItem[]) {
  return Array.from(
    new Set(
      items
        .filter((item) => item.category === "vector_index")
        .flatMap((item) => item.paths)
        .filter(Boolean),
    ),
  );
}

function AdminIndexPill({ label, item }: { label: string; item: DashboardIndexSummary }) {
  return (
    <span className={`admin-index-pill dashboard-index-${item.status}`}>
      {label}: {dashboardIndexStatusLabel(item.status)} ({item.indexed_chunks}/{item.parsed_chunks})
    </span>
  );
}

function DashboardIndexCard({
  label,
  item,
  onNavigate,
}: {
  label: string;
  item: DashboardIndexSummary | null;
  onNavigate: (view: View) => void;
}) {
  const status = item?.status ?? "missing";
  return (
    <section className={`card dashboard-index-card dashboard-index-${status}`} data-dashboard-status={status}>
      <div className="row row-between">
        <div>
          <div className="eyebrow">{label} index</div>
          <h2>{dashboardIndexStatusLabel(status)}</h2>
        </div>
        <span className={`badge ${item?.ready ? "badge-ok" : "badge-warn"}`}>
          <span className="dot" />
          {item?.ready ? "Ready" : "Needs attention"}
        </span>
      </div>
      <p>{item?.message ?? "Dashboard summary has not loaded yet."}</p>
      <dl className="kv dashboard-kv">
        <dt>indexed chunks</dt>
        <dd>{item?.indexed_chunks ?? 0}</dd>
        <dt>parsed chunks</dt>
        <dd>{item?.parsed_chunks ?? 0}</dd>
        <dt>model</dt>
        <dd>{item?.model ?? "not applicable"}</dd>
      </dl>
      <div className="dashboard-actions">
        <button className="btn btn-sm" type="button" onClick={() => onNavigate("search")}>
          Open Search Lab
        </button>
        <button className="btn btn-sm" type="button" onClick={() => onNavigate("chat")}>
          Open Chat Workspace
        </button>
      </div>
    </section>
  );
}

function DashboardMetric({
  label,
  value,
  detail,
}: {
  label: string;
  value: string | number;
  detail: string;
}) {
  return (
    <article className="dashboard-metric">
      <span>{label}</span>
      <strong>{value}</strong>
      <small>{detail}</small>
    </article>
  );
}

function SettingsModels({
  repository,
  settings,
  chatModelRegistry,
  modelCatalog,
  dashboardSummary,
  onNavigate,
  onSave,
  onAnalyzeImpact,
  onCheckReadiness,
}: {
  repository: RepositoryResponse["repository"] | null;
  settings: RepositorySettings | null;
  chatModelRegistry: ChatModelRegistry | null;
  modelCatalog: RepositoryModelCatalog | null;
  dashboardSummary: DashboardSummary | null;
  onNavigate: (view: View) => void;
  onSave: (settings: RepositorySettings) => Promise<RepositorySettings>;
  onAnalyzeImpact: (settings: RepositorySettings) => Promise<SettingsImpactResponse>;
  onCheckReadiness: () => Promise<SettingsReadinessResponse>;
}) {
  const [draft, setDraft] = useState<RepositorySettings | null>(() => cloneSettings(settings));
  const [saveMessage, setSaveMessage] = useState("Loaded repository defaults");
  const [saveBusy, setSaveBusy] = useState(false);
  const [pendingImpact, setPendingImpact] = useState<SettingsImpactResponse | null>(null);
  const [lastSavedImpact, setLastSavedImpact] = useState<SettingsImpactResponse | null>(null);
  const [impactMessage, setImpactMessage] = useState("No pending settings impact.");
  const [readiness, setReadiness] = useState<SettingsReadinessResponse | null>(null);
  const [readinessBusy, setReadinessBusy] = useState(false);
  const [readinessMessage, setReadinessMessage] = useState("Readiness has not been checked.");
  const lastRepositoryId = useRef(repository?.id ?? null);

  useEffect(() => {
    if (lastRepositoryId.current !== repository?.id) {
      lastRepositoryId.current = repository?.id ?? null;
      setLastSavedImpact(null);
      setImpactMessage("No pending settings impact.");
    }
    setDraft(cloneSettings(settings));
    setSaveMessage("Loaded repository defaults");
    setPendingImpact(null);
    setReadiness(null);
    setReadinessMessage("Readiness has not been checked.");
  }, [settings, repository?.id]);

  const validationIssues = useMemo(() => validateSettingsDraft(draft, modelCatalog), [draft, modelCatalog]);
  const validationByField = useMemo(
    () => new Map(validationIssues.map((issue) => [issue.field, issue.message])),
    [validationIssues],
  );
  const requiredModels = requiredModelsForSettings(draft);
  const embeddingCatalog = modelCatalog?.embedding_models ?? [];
  const selectedEmbeddingModel = embeddingCatalog.find(
    (model) => model.provider === draft?.embedding.provider && model.model === draft.embedding.model,
  );
  const embeddingProviders = Array.from(
    new Set(
      [draft?.embedding.provider, ...embeddingCatalog.map((model) => model.provider)].filter(
        (provider): provider is string => Boolean(provider),
      ),
    ),
  );
  const providerEmbeddingModels = embeddingCatalog.filter(
    (model) => model.provider === draft?.embedding.provider,
  );
  const embeddingModelSelectValue = selectedEmbeddingModel?.model ?? "__custom__";
  const distanceOptions = ["cosine", "dot", "euclid"];
  const disabledDistanceOptions = selectedEmbeddingModel
    ? distanceOptions.filter((distance) => !selectedEmbeddingModel.supported_distances.includes(distance))
    : draft?.embedding.provider === "ollama"
      ? ["dot", "euclid"]
      : [];
  const chatCatalog =
    modelCatalog?.chat_models ??
    chatModelRegistry?.models.map((model) => ({ ...model, source: "known" as ModelCatalogSource })) ??
    [];
  const selectedChatModelInfo = chatCatalog.find(
    (model) => model.name === draft?.model.ollama_chat_model,
  );
  const rerankerCatalog = modelCatalog?.reranker_models ?? [];
  const selectedRerankerOption =
    draft?.reranking.strategy === "none"
      ? "__none__"
      : rerankerCatalog.find(
          (entry) => entry.strategy === draft?.reranking.strategy && entry.model === draft.reranking.model,
        )?.model ?? "__custom__";
  const parserCatalog = modelCatalog?.parser_choices ?? defaultParserCatalog();
  const structuredParserChoices = parserCatalog.filter((entry) =>
    entry.supported_as.includes("structured"),
  );
  const fallbackParserChoices = parserCatalog.filter((entry) =>
    entry.supported_as.includes("fallback"),
  );
  const parserLabels = Object.fromEntries(
    parserCatalog.map((entry) => [entry.id, entry.label]),
  );
  const selectedStructuredParser = parserCatalog.find(
    (entry) => entry.id === draft?.parser.structured_parser,
  );
  const selectedFallbackParser = parserCatalog.find(
    (entry) => entry.id === draft?.parser.fallback_parser,
  );
  const collectionChanged = Boolean(
    settings && draft && settings.vector.collection_name !== draft.vector.collection_name,
  );
  const collectionStatus = collectionChanged
    ? "stale"
    : dashboardSummary?.vector.status ?? "not_checked";
  const collectionStatusText = collectionChanged
    ? "Stale until rebuild"
    : collectionStatus === "not_checked"
      ? "Not checked"
      : dashboardIndexStatusLabel(collectionStatus);
  const collectionMessage = collectionChanged
    ? "Changing the collection name does not migrate vectors. Save settings, then rebuild vectors before search uses the new collection."
    : dashboardSummary?.vector.message ??
      "Collection state has not been checked for this repository in the current dashboard summary.";
  const dirty = Boolean(settings && draft && JSON.stringify(settings) !== JSON.stringify(draft));
  const visibleImpact = dirty ? pendingImpact : lastSavedImpact;

  useEffect(() => {
    let cancelled = false;
    if (!draft || !dirty || validationIssues.length > 0) {
      setPendingImpact(null);
      if (validationIssues.length > 0) {
        setImpactMessage("Fix validation errors to preview impact.");
      } else if (!lastSavedImpact) {
        setImpactMessage("No pending settings impact.");
      }
      return () => {
        cancelled = true;
      };
    }

    setImpactMessage("Checking settings impact...");
    onAnalyzeImpact(draft)
      .then((impact) => {
        if (!cancelled) {
          setPendingImpact(impact);
          setImpactMessage(
            impact.impacts.length > 0
              ? "Review impact before saving."
              : "No rebuild or workflow impact detected.",
          );
        }
      })
      .catch(() => {
        if (!cancelled) {
          setPendingImpact(null);
          setImpactMessage("Settings impact unavailable.");
        }
      });

    return () => {
      cancelled = true;
    };
  }, [draft, dirty, repository?.id, validationIssues, lastSavedImpact]);

  function updateDraft(updater: (next: RepositorySettings) => void) {
    setDraft((current) => {
      if (!current) {
        return current;
      }
      const next = cloneSettings(current);
      if (!next) {
        return current;
      }
      updater(next);
      return next;
    });
  }

  async function handleSave() {
    if (!draft) {
      setSaveMessage("Settings unavailable");
      return;
    }
    if (validationIssues.length > 0) {
      setSaveMessage("Fix validation errors before saving");
      return;
    }
    setSaveBusy(true);
    setSaveMessage("Saving settings...");
    const impactBeforeSave = pendingImpact;
    try {
      const saved = await onSave(draft);
      setDraft(cloneSettings(saved));
      setLastSavedImpact(impactBeforeSave);
      setPendingImpact(null);
      setImpactMessage(
        impactBeforeSave?.impacts.length
          ? "Saved settings changed repository readiness. Review the follow-up actions."
          : "Settings saved with no rebuild or workflow impact.",
      );
      setSaveMessage("Settings saved");
    } catch (error) {
      setSaveMessage(error instanceof Error ? error.message : "Settings save failed");
    } finally {
      setSaveBusy(false);
    }
  }

  function cancelEdits() {
    setDraft(cloneSettings(settings));
    setPendingImpact(null);
    setSaveMessage("Edits discarded");
  }

  async function runReadinessCheck() {
    setReadinessBusy(true);
    setReadinessMessage("Checking local readiness...");
    try {
      const result = await onCheckReadiness();
      setReadiness(result);
      setReadinessMessage("Readiness check complete.");
    } catch (error) {
      setReadiness(null);
      setReadinessMessage(
        error instanceof Error ? error.message : "Settings readiness check failed",
      );
    } finally {
      setReadinessBusy(false);
    }
  }

  function updatePromptEntry(
    promptId: string,
    field: "name" | "text",
    value: string,
  ) {
    updateDraft((next) => {
      next.prompt.library = next.prompt.library.map((prompt) =>
        prompt.id === promptId ? { ...prompt, [field]: value } : prompt,
      );
    });
  }

  function addPromptEntry() {
    updateDraft((next) => {
      const promptId = `chat-prompt-${Date.now()}`;
      next.prompt.library = [
        ...next.prompt.library,
        {
          id: promptId,
          name: "New chat prompt",
          text: "Answer from repository context and cite supporting evidence.",
        },
      ];
      next.prompt.active_chat_prompt_id = promptId;
    });
  }

  function removePromptEntry(promptId: string) {
    updateDraft((next) => {
      if (next.prompt.library.length <= 1) {
        return;
      }
      next.prompt.library = next.prompt.library.filter((prompt) => prompt.id !== promptId);
      if (next.prompt.active_chat_prompt_id === promptId) {
        next.prompt.active_chat_prompt_id = next.prompt.library[0]?.id ?? "";
      }
    });
  }

  function applyKnownEmbeddingModel(next: RepositorySettings, metadata: EmbeddingModelCatalogEntry) {
    next.embedding.provider = metadata.provider;
    next.embedding.model = metadata.model;
    next.vector.vector_size = metadata.vector_size;
    if (!metadata.supported_distances.includes(next.vector.distance)) {
      next.vector.distance = metadata.supported_distances[0] ?? "cosine";
    }
  }

  function selectEmbeddingProvider(provider: string) {
    updateDraft((next) => {
      const firstKnownModel = embeddingCatalog.find((model) => model.provider === provider);
      if (firstKnownModel) {
        applyKnownEmbeddingModel(next, firstKnownModel);
        return;
      }
      next.embedding.provider = provider;
    });
  }

  function selectEmbeddingModel(modelName: string) {
    updateDraft((next) => {
      if (modelName === "__custom__") {
        return;
      }
      const metadata = embeddingCatalog.find(
        (model) => model.provider === next.embedding.provider && model.model === modelName,
      );
      if (metadata) {
        applyKnownEmbeddingModel(next, metadata);
      }
    });
  }

  function selectChatModel(modelName: string) {
    if (modelName === "__custom__") {
      return;
    }
    updateDraft((next) => {
      next.model.ollama_chat_model = modelName;
    });
  }

  function selectRerankerModel(value: string) {
    updateDraft((next) => {
      if (value === "__none__") {
        next.reranking.strategy = "none";
        next.reranking.model = null;
        return;
      }
      next.reranking.strategy = "cross_encoder";
      if (value === "__custom__") {
        next.reranking.model = next.reranking.model ?? "";
        return;
      }
      const catalogEntry = rerankerCatalog.find((entry) => entry.model === value);
      next.reranking.model = catalogEntry?.model ?? value;
    });
  }

  if (!draft) {
    return (
      <div className="empty">
        <h3>Settings unavailable</h3>
        <p>Repository settings will appear here when the backend is available.</p>
      </div>
    );
  }

  return (
    <div className="settings-layout">
      <section className="card settings-overview">
        <div className="row row-between">
          <div>
            <div className="eyebrow">Repository settings</div>
            <h2>{repository?.name ?? "Default Repository"}</h2>
          </div>
          <span className={`badge ${validationIssues.length > 0 ? "badge-danger" : dirty ? "badge-warn" : "badge-ok"}`}>
            <span className="dot" />
            {validationIssues.length > 0 ? "Needs fixes" : dirty ? "Unsaved edits" : "Saved"}
          </span>
        </div>
        <div className="row row-between settings-save-row">
          <span className="muted">{saveMessage}</span>
          <div className="row">
            <button className="btn btn-ghost" type="button" onClick={cancelEdits} disabled={!dirty || saveBusy}>
              Cancel
            </button>
            <button
              className="btn btn-primary"
              type="button"
              onClick={() => void handleSave()}
              disabled={!dirty || saveBusy || validationIssues.length > 0}
            >
              {saveBusy ? "Saving..." : "Save settings"}
            </button>
          </div>
        </div>
        {validationIssues.length > 0 && (
          <div className="banner banner-warn settings-validation">
            <div>
              <strong>Validation</strong>
              <span>{validationIssues.map((issue) => issue.message).join(" ")}</span>
            </div>
          </div>
        )}
        <SettingsImpactPanel
          impact={visibleImpact}
          message={impactMessage}
          mode={dirty ? "pending" : "saved"}
          onNavigate={onNavigate}
        />
        <div className="settings-actions">
          <button className="btn btn-sm" type="button" onClick={() => onNavigate("documents")}>
            Document Manager
          </button>
          <button className="btn btn-sm" type="button" onClick={() => onNavigate("search")}>
            Search Lab
          </button>
          <button className="btn btn-sm" type="button" onClick={() => onNavigate("chat")}>
            Chat Workspace
          </button>
          <button className="btn btn-sm" type="button" onClick={() => onNavigate("sandbox")}>
            Prompt Sandbox
          </button>
          <button className="btn btn-sm" type="button" onClick={() => onNavigate("export")}>
            Export Center
          </button>
        </div>
      </section>

      <div className="settings-grid">
        <section className="card settings-section">
          <div className="eyebrow">Defaults</div>
          <h2>Chunking and parser</h2>
          <SettingSelect
            id="settings-chunking-mode"
            label="Chunking mode"
            value={draft.chunking.mode}
            options={["recursive", "semantic", "fixed"]}
            onChange={(value) => updateDraft((next) => { next.chunking.mode = value; })}
          />
          <SettingNumber
            id="settings-chunk-size"
            label="Chunk size"
            value={draft.chunking.chunk_size}
            error={validationByField.get("chunking.chunk_size")}
            onChange={(value) => updateDraft((next) => { next.chunking.chunk_size = value; })}
          />
          <SettingNumber
            id="settings-chunk-overlap"
            label="Chunk overlap"
            value={draft.chunking.chunk_overlap}
            error={validationByField.get("chunking.chunk_overlap")}
            onChange={(value) => updateDraft((next) => { next.chunking.chunk_overlap = value; })}
          />
          <SettingSelect
            id="settings-structured-parser"
            label="Structured parser"
            value={draft.parser.structured_parser}
            options={structuredParserChoices.map((entry) => entry.id)}
            labels={parserLabels}
            error={validationByField.get("parser.structured_parser")}
            onChange={(value) => updateDraft((next) => { next.parser.structured_parser = value; })}
          />
          {selectedStructuredParser && (
            <p className="settings-field-note">{selectedStructuredParser.notes}</p>
          )}
          <SettingSelect
            id="settings-fallback-parser"
            label="Fallback parser"
            value={draft.parser.fallback_parser}
            options={fallbackParserChoices.map((entry) => entry.id)}
            labels={parserLabels}
            error={validationByField.get("parser.fallback_parser")}
            onChange={(value) => updateDraft((next) => { next.parser.fallback_parser = value; })}
          />
          {selectedFallbackParser && (
            <p className="settings-field-note">{selectedFallbackParser.notes}</p>
          )}
          <SettingSelect
            id="settings-ocr-provider"
            label="OCR provider"
            value={draft.ocr.provider}
            options={["ocrmypdf_tesseract", "rapidocr"]}
            labels={{ ocrmypdf_tesseract: "OCRmyPDF + Tesseract", rapidocr: "RapidOCR" }}
            error={validationByField.get("ocr.provider")}
            onChange={(value) => updateDraft((next) => { next.ocr.provider = value as RepositorySettings["ocr"]["provider"]; })}
          />
          <SettingSelect
            id="settings-ocr-fallback-provider"
            label="OCR fallback"
            value={draft.ocr.fallback_provider}
            options={["none", "ocrmypdf_tesseract", "rapidocr"]}
            labels={{ none: "None", ocrmypdf_tesseract: "OCRmyPDF + Tesseract", rapidocr: "RapidOCR" }}
            error={validationByField.get("ocr.fallback_provider")}
            onChange={(value) => updateDraft((next) => { next.ocr.fallback_provider = value as RepositorySettings["ocr"]["fallback_provider"]; })}
          />
          <SettingNumber
            id="settings-ocr-confidence"
            label="OCR confidence threshold"
            value={draft.ocr.confidence_threshold}
            error={validationByField.get("ocr.confidence_threshold")}
            onChange={(value) => updateDraft((next) => { next.ocr.confidence_threshold = value; })}
          />
          <SettingNumber
            id="settings-ocr-min-text"
            label="OCR minimum text"
            value={draft.ocr.min_text_length}
            error={validationByField.get("ocr.min_text_length")}
            onChange={(value) => updateDraft((next) => { next.ocr.min_text_length = value; })}
          />
          <SettingNumber
            id="settings-ocr-max-pages"
            label="OCR max pages"
            value={draft.ocr.max_pages}
            error={validationByField.get("ocr.max_pages")}
            onChange={(value) => updateDraft((next) => { next.ocr.max_pages = value; })}
          />
          <SettingText
            id="settings-ocr-language"
            label="OCR language"
            value={draft.ocr.language}
            error={validationByField.get("ocr.language")}
            onChange={(value) => updateDraft((next) => { next.ocr.language = value; })}
          />
          <label className="settings-checkbox">
            <input
              type="checkbox"
              checked={draft.ocr.fallback_enabled}
              onChange={(event) => updateDraft((next) => { next.ocr.fallback_enabled = event.target.checked; })}
            />
            <span>Use OCR fallback when quality is low</span>
          </label>
          <label className="settings-checkbox">
            <input
              type="checkbox"
              checked={draft.ocr.overwrite}
              onChange={(event) => updateDraft((next) => { next.ocr.overwrite = event.target.checked; })}
            />
            <span>Overwrite existing OCR artifacts</span>
          </label>
        </section>

        <section className="card settings-section">
          <div className="eyebrow">Defaults</div>
          <h2>Full-text</h2>
          <SettingSelect
            id="settings-tokenizer"
            label="Tokenizer"
            value={draft.full_text.tokenizer}
            options={["unicode61", "porter"]}
            onChange={(value) => updateDraft((next) => { next.full_text.tokenizer = value; })}
          />
          <SettingCheckbox
            id="settings-prefix-index"
            label="Prefix index"
            checked={draft.full_text.prefix_index}
            onChange={(value) => updateDraft((next) => { next.full_text.prefix_index = value; })}
          />
          <SettingCheckbox
            id="settings-porter-stemming"
            label="Porter stemming"
            checked={draft.full_text.porter_stemming}
            onChange={(value) => updateDraft((next) => { next.full_text.porter_stemming = value; })}
          />
        </section>

        <section className="card settings-section">
          <div className="eyebrow">Defaults</div>
          <h2>Vector and embedding</h2>
          <SettingSelect
            id="settings-embedding-provider"
            label="Embedding provider"
            value={draft.embedding.provider}
            options={embeddingProviders}
            onChange={selectEmbeddingProvider}
          />
          {providerEmbeddingModels.length > 0 && (
            <SettingSelect
              id="settings-known-embedding-model"
              label="Known embedding model"
              value={embeddingModelSelectValue}
              options={["__custom__", ...providerEmbeddingModels.map((model) => model.model)]}
              labels={{
                __custom__: "Custom embedding model",
                ...Object.fromEntries(
                  providerEmbeddingModels.map((model) => [
                    model.model,
                    `${model.label} · ${model.vector_size} dimensions`,
                  ]),
                ),
              }}
              onChange={selectEmbeddingModel}
            />
          )}
          {!selectedEmbeddingModel && (
            <SettingText
              id="settings-embedding-model"
              label="Custom embedding model"
              value={draft.embedding.model}
              error={validationByField.get("embedding.model")}
              onChange={(value) => updateDraft((next) => { next.embedding.model = value; })}
            />
          )}
          <div className="settings-model-guidance settings-embedding-guidance">
            <strong>{selectedEmbeddingModel?.label ?? "Advanced custom embedding model"}</strong>
            <small>
              {selectedEmbeddingModel?.resource_notes ??
                "Custom models remain available, but verify vector dimensions before rebuilding."}
            </small>
            <small>
              {selectedEmbeddingModel?.setup_hint ??
                (draft.embedding.provider === "ollama"
                  ? "Custom Ollama embeddings require cosine distance and a live dimension probe before rebuild."
                  : "Custom SentenceTransformers models should be cached locally and dimension-checked before rebuild.")}
            </small>
          </div>
          <SettingText
            id="settings-vector-collection"
            label="Qdrant collection"
            value={draft.vector.collection_name}
            error={validationByField.get("vector.collection_name")}
            onChange={(value) => updateDraft((next) => { next.vector.collection_name = value; })}
          />
          <div className={`settings-collection-info settings-collection-${collectionStatus}`}>
            <div className="row row-between">
              <strong>Collection state</strong>
              <span className="badge">
                <span className="dot" />
                {collectionStatusText}
              </span>
            </div>
            <p>
              Vector rebuild writes this collection, and vector search reads the latest active vector
              index for this repository.
            </p>
            <small>{collectionMessage}</small>
            <div className="settings-readiness-actions">
              <button className="btn btn-sm" type="button" onClick={() => onNavigate("search")}>
                Open Search Lab
              </button>
              <button className="btn btn-sm" type="button" onClick={() => onNavigate("admin")}>
                Open Repository Administration
              </button>
            </div>
          </div>
          <SettingNumber
            id="settings-vector-size"
            label="Vector size"
            value={draft.vector.vector_size}
            error={validationByField.get("vector.vector_size")}
            disabled={Boolean(selectedEmbeddingModel)}
            onChange={(value) => updateDraft((next) => { next.vector.vector_size = value; })}
          />
          <SettingSelect
            id="settings-vector-distance"
            label="Distance"
            value={draft.vector.distance}
            options={distanceOptions}
            disabledOptions={disabledDistanceOptions}
            error={validationByField.get("vector.distance")}
            onChange={(value) => updateDraft((next) => { next.vector.distance = value; })}
          />
        </section>

        <section className="card settings-section">
          <div className="eyebrow">Defaults</div>
          <h2>Reranking</h2>
          <SettingSelect
            id="settings-reranking-model-choice"
            label="Reranker"
            value={selectedRerankerOption}
            options={[
              "__none__",
              "__custom__",
              ...rerankerCatalog.filter((entry) => entry.enabled && entry.model).map((entry) => entry.model!),
            ]}
            labels={{
              __none__: "No reranking",
              __custom__: "Custom cross-encoder",
              ...Object.fromEntries(
                rerankerCatalog
                  .filter((entry) => entry.model)
                  .map((entry) => [entry.model!, `${entry.label} · ${modelSourceLabel(entry.source)}`]),
              ),
            }}
            onChange={selectRerankerModel}
          />
          {selectedRerankerOption === "__custom__" && draft.reranking.strategy !== "none" && (
            <SettingText
              id="settings-reranking-model"
              label="Custom reranker model"
              value={draft.reranking.model ?? ""}
              error={validationByField.get("reranking.model")}
              onChange={(value) => updateDraft((next) => { next.reranking.model = value; })}
            />
          )}
          <div className="settings-model-guidance">
            <strong>
              {draft.reranking.strategy === "none"
                ? "Reranking disabled"
                : rerankerCatalog.find((entry) => entry.model === draft.reranking.model)?.label ??
                  "Custom cross-encoder"}
            </strong>
            <small>
              {draft.reranking.strategy === "none"
                ? "Baseline retrieval ranking will be used without a local cross-encoder."
                : rerankerCatalog.find((entry) => entry.model === draft.reranking.model)?.resource_notes ??
                  "Custom cross-encoders should be cached locally before readiness checks or reranked search."}
            </small>
          </div>
        </section>

        <section className="card settings-section">
          <div className="eyebrow">Repository defaults</div>
          <h2>Retrieval defaults</h2>
          <SettingSelect
            id="settings-retrieval-mode"
            label="Mode"
            value={draft.retrieval.mode}
            options={["full_text", "vector", "hybrid"]}
            labels={{ full_text: "Full-text", vector: "Vector", hybrid: "Hybrid" }}
            onChange={(value) => updateDraft((next) => { next.retrieval.mode = value as RetrievalDefaults["mode"]; })}
          />
          <SettingNumber
            id="settings-retrieval-top-k"
            label="Final top-k"
            value={draft.retrieval.top_k}
            error={validationByField.get("retrieval.top_k")}
            onChange={(value) => updateDraft((next) => { next.retrieval.top_k = value; })}
          />
          <SettingCheckbox
            id="settings-retrieval-candidate-auto"
            label="Use automatic candidate pool"
            checked={draft.retrieval.candidate_pool_size == null}
            onChange={(value) => updateDraft((next) => {
              next.retrieval.candidate_pool_size = value ? null : next.retrieval.top_k * 5;
            })}
          />
          {draft.retrieval.candidate_pool_size != null && (
            <SettingNumber
              id="settings-retrieval-candidate-pool"
              label="Candidate pool"
              value={draft.retrieval.candidate_pool_size}
              error={validationByField.get("retrieval.candidate_pool_size")}
              onChange={(value) => updateDraft((next) => { next.retrieval.candidate_pool_size = value; })}
            />
          )}
          <SettingNumber
            id="settings-retrieval-rrf"
            label="RRF constant"
            value={draft.retrieval.rrf_constant}
            error={validationByField.get("retrieval.rrf_constant")}
            onChange={(value) => updateDraft((next) => { next.retrieval.rrf_constant = value; })}
          />
          <SettingSelect
            id="settings-retrieval-reranker-strategy"
            label="Ranking strategy"
            value={draft.retrieval.reranker_strategy}
            options={["none", "cross_encoder", "metadata_boost", "cross_encoder_metadata_boost"]}
            labels={{
              none: "No reranking",
              cross_encoder: "Cross-encoder",
              metadata_boost: "Metadata boost",
              cross_encoder_metadata_boost: "Cross-encoder + metadata boost",
            }}
            onChange={(value) => updateDraft((next) => { next.retrieval.reranker_strategy = value as RerankerStrategy; })}
          />
          <div className="settings-model-guidance">
            <strong>Metadata display is separate from ranking boost</strong>
            <small>Result metadata can still be shown when a boost dimension is off.</small>
            <small>New chat sessions snapshot these defaults. Existing sessions keep their saved settings.</small>
          </div>
          <div className="settings-subgrid">
            {(["section", "patent_section", "document_kind", "table_figure"] as const).map((key) => (
              <SettingSelect
                id={`settings-retrieval-boost-${key}`}
                key={key}
                label={metadataBoostLabel(key)}
                value={draft.retrieval.metadata_boosts[key]}
                options={["off", "low", "medium", "high"]}
                labels={{ off: "Off", low: "Low", medium: "Medium", high: "High" }}
                onChange={(value) => updateDraft((next) => {
                  next.retrieval.metadata_boosts[key] = value as MetadataBoostSettings[typeof key];
                })}
              />
            ))}
          </div>
          <SettingText
            id="settings-retrieval-filter-document-kind"
            label="Default document kind filter"
            value={draft.retrieval.filters.document_kind ?? ""}
            onChange={(value) => updateDraft((next) => {
              next.retrieval.filters.document_kind = value.trim() || null;
            })}
          />
          <SettingText
            id="settings-retrieval-filter-section"
            label="Default section filter"
            value={draft.retrieval.filters.section ?? ""}
            onChange={(value) => updateDraft((next) => {
              next.retrieval.filters.section = value.trim() || null;
            })}
          />
          <SettingText
            id="settings-retrieval-filter-patent-section"
            label="Default patent section filter"
            value={draft.retrieval.filters.patent_section ?? ""}
            onChange={(value) => updateDraft((next) => {
              next.retrieval.filters.patent_section = value.trim() || null;
            })}
          />
        </section>

        <section className="card settings-section">
          <div className="eyebrow">Defaults</div>
          <h2>Chat defaults</h2>
          {chatCatalog.length > 0 && (
            <SettingSelect
              id="settings-known-chat-model"
              label="Chat model"
              value={selectedChatModelInfo?.name ?? "__custom__"}
              options={["__custom__", ...chatCatalog.map((model) => model.name)]}
              labels={{
                __custom__: "Custom local Ollama model",
                ...Object.fromEntries(
                  chatCatalog.map((model) => [
                    model.name,
                    `${model.label} · ${chatModelRoleLabel(model.role)} · ${modelSourceLabel(model.source)}`,
                  ]),
                ),
              }}
              onChange={selectChatModel}
            />
          )}
          {!selectedChatModelInfo && (
            <SettingText
              id="settings-chat-model"
              label="Custom chat model"
              value={draft.model.ollama_chat_model}
              error={validationByField.get("model.ollama_chat_model")}
              onChange={(value) => updateDraft((next) => { next.model.ollama_chat_model = value; })}
            />
          )}
          <div className="settings-model-guidance">
            <strong>{selectedChatModelInfo?.label ?? "Custom local Ollama model"}</strong>
            <small>
              {selectedChatModelInfo?.notes ??
                "Any local Ollama model can be used here when it supports the normal /api/chat contract."}
            </small>
            <small>
              Normal Chat Workspace sessions search local repository context by default using chat-owned
              retrieval settings, then send that context to this Ollama model.
            </small>
            <small>
              {selectedChatModelInfo?.setup_command ??
                `Run ollama pull ${draft.model.ollama_chat_model || "<model>"} before checking readiness.`}
            </small>
            <small>{modelCatalog?.runtime_detection.message ?? "Runtime model detection has not been run."}</small>
          </div>
          <SettingSelect
            id="settings-active-prompt"
            label="Active chat prompt"
            value={draft.prompt.active_chat_prompt_id}
            options={draft.prompt.library.map((prompt) => prompt.id)}
            labels={Object.fromEntries(draft.prompt.library.map((prompt) => [prompt.id, prompt.name]))}
            error={validationByField.get("prompt.active_chat_prompt_id")}
            onChange={(value) => updateDraft((next) => { next.prompt.active_chat_prompt_id = value; })}
          />
          <span className="muted">{draft.prompt.library.length} prompt library entries</span>
        </section>

        <section className="card settings-section">
          <div className="eyebrow">Defaults</div>
          <h2>Export defaults</h2>
          <SettingCheckbox
            id="settings-export-sources"
            label="Include sources"
            checked={draft.export.include_sources}
            onChange={(value) => updateDraft((next) => { next.export.include_sources = value; })}
          />
          <SettingCheckbox
            id="settings-export-indexes"
            label="Include indexes"
            checked={draft.export.include_indexes}
            onChange={(value) => updateDraft((next) => { next.export.include_indexes = value; })}
          />
          <SettingSelect
            id="settings-export-format"
            label="Format"
            value={draft.export.format}
            options={["json"]}
            onChange={(value) => updateDraft((next) => { next.export.format = value; })}
          />
        </section>
      </div>

      <section className="card settings-prompts">
        <div className="row row-between">
          <div>
            <div className="eyebrow">Chat prompt library</div>
            <h2>Normal chat prompts</h2>
          </div>
          <button className="btn btn-sm" type="button" onClick={addPromptEntry}>
            Add prompt
          </button>
        </div>
        <div className="settings-prompt-list">
          {draft.prompt.library.map((prompt, index) => (
            <div className="settings-prompt-row" key={prompt.id}>
              <div className="row row-between">
                <strong>Prompt {index + 1}</strong>
                <button
                  className="btn btn-sm btn-ghost danger-action"
                  type="button"
                  onClick={() => removePromptEntry(prompt.id)}
                  disabled={draft.prompt.library.length <= 1}
                >
                  Remove
                </button>
              </div>
              <SettingText
                id={`settings-prompt-name-${prompt.id}`}
                label="Name"
                value={prompt.name}
                error={validationByField.get(`prompt.library.${prompt.id}.name`)}
                onChange={(value) => updatePromptEntry(prompt.id, "name", value)}
              />
              <SettingTextarea
                id={`settings-prompt-text-${prompt.id}`}
                label="Prompt text"
                value={prompt.text}
                error={validationByField.get(`prompt.library.${prompt.id}.text`)}
                onChange={(value) => updatePromptEntry(prompt.id, "text", value)}
              />
            </div>
          ))}
        </div>
      </section>

      <section className="card settings-models">
        <div className="row row-between">
          <div>
            <div className="eyebrow">Model readiness</div>
            <h2>Configured local models</h2>
          </div>
          <button
            className={`btn btn-primary ${readinessBusy ? "btn-running" : ""}`}
            type="button"
            onClick={() => void runReadinessCheck()}
            disabled={readinessBusy || !repository || dirty || validationIssues.length > 0}
            aria-busy={readinessBusy}
          >
            {readinessBusy ? "Checking..." : "Check readiness"}
          </button>
        </div>
        <p className="muted">
          {dirty
            ? "Save settings before checking readiness."
            : validationIssues.length > 0
              ? "Fix validation errors before checking readiness."
              : readinessMessage}
        </p>
        <div className="settings-readiness-grid">
          {settingsReadinessItems(readiness, draft).map((item) => (
            <ReadinessCard item={item} key={item.target} onNavigate={onNavigate} />
          ))}
        </div>
        <div className="export-chip-list settings-chip-list">
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
  );
}

function SettingText({
  id,
  label,
  value,
  error,
  disabled = false,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  error?: string;
  disabled?: boolean;
  onChange: (value: string) => void;
}) {
  return (
    <label className="settings-field" htmlFor={id}>
      <span>{label}</span>
      <input id={id} value={value} disabled={disabled} onChange={(event) => onChange(event.target.value)} />
      {error && <small className="settings-field-error">{error}</small>}
    </label>
  );
}

function SettingsImpactPanel({
  impact,
  message,
  mode,
  onNavigate,
}: {
  impact: SettingsImpactResponse | null;
  message: string;
  mode: "pending" | "saved";
  onNavigate: (view: View) => void;
}) {
  const impacts = impact?.impacts ?? [];
  return (
    <section className="settings-impact" aria-label="Settings impact">
      <div className="row row-between">
        <div>
          <div className="eyebrow">{mode === "pending" ? "Pending impact" : "Saved impact"}</div>
          <h2>Rebuild and workflow effects</h2>
        </div>
        <span className={`badge ${impacts.length > 0 ? "badge-warn" : "badge-ok"}`}>
          <span className="dot" />
          {impacts.length > 0 ? `${impacts.length} changes` : "No impact"}
        </span>
      </div>
      <p className="muted">{message}</p>
      {impacts.length > 0 && (
        <div className="settings-impact-list">
          {impacts.map((item) => (
            <article className={`settings-impact-item settings-impact-${item.severity}`} key={item.category}>
              <div className="row row-between">
                <strong>{item.title}</strong>
                <span className="badge">
                  <span className="dot" />
                  {item.category.replace(/_/g, " ")}
                </span>
              </div>
              <p>{item.message}</p>
              {item.actions.length > 0 && <small>{item.actions.join(" ")}</small>}
              {item.fields.length > 0 && (
                <div className="settings-impact-fields">
                  {item.fields.map((field) => (
                    <code key={field}>{field}</code>
                  ))}
                </div>
              )}
              <div className="settings-impact-actions">
                {workflowLinksForImpact(item).map((link) => (
                  <button className="btn btn-sm" type="button" onClick={() => onNavigate(link.view)} key={link.view}>
                    {link.label}
                  </button>
                ))}
              </div>
            </article>
          ))}
        </div>
      )}
    </section>
  );
}

function SettingTextarea({
  id,
  label,
  value,
  error,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  error?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="settings-field" htmlFor={id}>
      <span>{label}</span>
      <textarea id={id} rows={4} value={value} onChange={(event) => onChange(event.target.value)} />
      {error && <small className="settings-field-error">{error}</small>}
    </label>
  );
}

function SettingNumber({
  id,
  label,
  value,
  error,
  disabled = false,
  onChange,
}: {
  id: string;
  label: string;
  value: number;
  error?: string;
  disabled?: boolean;
  onChange: (value: number) => void;
}) {
  return (
    <label className="settings-field" htmlFor={id}>
      <span>{label}</span>
      <input
        id={id}
        type="number"
        value={Number.isFinite(value) ? value : 0}
        disabled={disabled}
        onChange={(event) => onChange(Number(event.target.value))}
      />
      {error && <small className="settings-field-error">{error}</small>}
    </label>
  );
}

function SettingSelect({
  id,
  label,
  value,
  options,
  labels = {},
  disabledOptions = [],
  error,
  onChange,
}: {
  id: string;
  label: string;
  value: string;
  options: string[];
  labels?: Record<string, string>;
  disabledOptions?: string[];
  error?: string;
  onChange: (value: string) => void;
}) {
  return (
    <label className="settings-field" htmlFor={id}>
      <span>{label}</span>
      <select id={id} value={value} onChange={(event) => onChange(event.target.value)}>
        {options.map((option) => (
          <option value={option} key={option} disabled={disabledOptions.includes(option)}>
            {labels[option] ?? option}
          </option>
        ))}
      </select>
      {error && <small className="settings-field-error">{error}</small>}
    </label>
  );
}

function SettingCheckbox({
  id,
  label,
  checked,
  onChange,
}: {
  id: string;
  label: string;
  checked: boolean;
  onChange: (value: boolean) => void;
}) {
  return (
    <label className="settings-checkbox" htmlFor={id}>
      <input id={id} type="checkbox" checked={checked} onChange={(event) => onChange(event.target.checked)} />
      <span>{label}</span>
    </label>
  );
}

function ReadinessCard({
  item,
  onNavigate,
}: {
  item: SettingsReadinessItem;
  onNavigate: (view: View) => void;
}) {
  const links = workflowLinksForReadiness(item);
  return (
    <div className={`settings-readiness-card settings-readiness-${item.status}`}>
      <span>{item.label}</span>
      <strong>{item.model ?? item.target}</strong>
      <em>{settingsReadinessStatusLabel(item.status)}</em>
      <small>{item.message}</small>
      {links.length > 0 && (
        <div className="settings-readiness-actions">
          {links.map((link) => (
            <button className="btn btn-sm" type="button" onClick={() => onNavigate(link.view)} key={link.view}>
              {link.label}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}

function PromptSandbox({
  prompts,
  chatModelRegistry,
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
  chatModelRegistry: ChatModelRegistry | null;
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
                list="sandbox-model-options"
                value={model}
                onChange={(event) => onModelChange(event.target.value)}
              />
              <datalist id="sandbox-model-options">
                {chatModelRegistry?.models.map((entry) => (
                  <option value={entry.name} key={entry.name}>
                    {entry.label}
                  </option>
                ))}
              </datalist>
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
  defaultIncludeSources,
  defaultIncludeIndexes,
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
  defaultIncludeSources: boolean;
  defaultIncludeIndexes: boolean;
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
            <div className="export-default-note">
              <strong>Saved export defaults</strong>
              <small>
                Sources {defaultIncludeSources ? "included" : "excluded"} · indexes{" "}
                {defaultIncludeIndexes ? "included" : "excluded"} · sandbox remains per export
              </small>
            </div>
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
        <dt>pool</dt>
        <dd>{progressRun.retrieval_settings.candidate_pool_size ?? progressRun.retrieval_settings.top_k * 5}</dd>
        <dt>RRF</dt>
        <dd>{progressRun.retrieval_settings.rrf_constant}</dd>
        <dt>strategy</dt>
        <dd>{progressRun.retrieval_settings.reranker_strategy.replace(/_/g, " ")}</dd>
        <dt>boosts</dt>
        <dd>
          {Object.values(progressRun.retrieval_settings.metadata_boosts).some((level) => level !== "off")
            ? "some on"
            : "off"}
        </dd>
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
  settings,
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
  settings: RepositorySettings | null;
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
  const activePrompt = settings?.prompt.library.find(
    (prompt) => prompt.id === settings.prompt.active_chat_prompt_id,
  );
  const chatDefaultModel = settings?.model.ollama_chat_model ?? "gemma3:4b";
  const configuredEmbeddingModel = settings
    ? `${settings.embedding.provider} / ${shortModelName(settings.embedding.model)}`
    : "embedding unavailable";
  const latestVectorModel = readiness?.vector.model
    ? shortModelName(readiness.vector.model)
    : "no vector index model yet";

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
            <div className="grid grid-3 chat-settings-controls">
              <div>
                <label className="field" htmlFor="chat-candidate-pool">
                  Candidate pool
                </label>
                <select
                  id="chat-candidate-pool"
                  value={retrievalSettings.candidate_pool_size ?? ""}
                  onChange={(event) =>
                    onRetrievalSettingsChange({
                      ...retrievalSettings,
                      candidate_pool_size: event.target.value ? Number(event.target.value) : null,
                    })
                  }
                >
                  <option value="">Auto</option>
                  {[25, 50, 100, 150, 250].map((value) => (
                    <option value={value} key={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="field" htmlFor="chat-rrf">
                  RRF constant
                </label>
                <select
                  id="chat-rrf"
                  value={retrievalSettings.rrf_constant}
                  onChange={(event) =>
                    onRetrievalSettingsChange({
                      ...retrievalSettings,
                      rrf_constant: Number(event.target.value),
                    })
                  }
                >
                  {[10, 30, 60, 100].map((value) => (
                    <option value={value} key={value}>
                      {value}
                    </option>
                  ))}
                </select>
              </div>
              <div>
                <label className="field" htmlFor="chat-filter-document-kind">
                  Document kind
                </label>
                <input
                  id="chat-filter-document-kind"
                  value={retrievalSettings.filters.document_kind ?? ""}
                  onChange={(event) =>
                    onRetrievalSettingsChange({
                      ...retrievalSettings,
                      filters: {
                        ...retrievalSettings.filters,
                        document_kind: event.target.value.trim() || null,
                      },
                    })
                  }
                  placeholder="patent_pdf"
                />
              </div>
            </div>
            <div className="grid grid-4 chat-settings-controls">
              {(["section", "patent_section", "document_kind", "table_figure"] as const).map((key) => (
                <div key={key}>
                  <label className="field" htmlFor={`chat-boost-${key}`}>
                    {metadataBoostLabel(key)}
                  </label>
                  <select
                    id={`chat-boost-${key}`}
                    value={retrievalSettings.metadata_boosts[key]}
                    onChange={(event) =>
                      onRetrievalSettingsChange({
                        ...retrievalSettings,
                        metadata_boosts: {
                          ...retrievalSettings.metadata_boosts,
                          [key]: event.target.value as MetadataBoostSettings[typeof key],
                        },
                      })
                    }
                  >
                    <option value="off">Off</option>
                    <option value="low">Low</option>
                    <option value="medium">Medium</option>
                    <option value="high">High</option>
                  </select>
                </div>
              ))}
            </div>
            <div className="chat-defaults-note">
              <strong>Effective retrieval</strong>
              <small>
                {retrievalSettings.mode} · top-{retrievalSettings.top_k} · pool{" "}
                {retrievalSettings.candidate_pool_size ?? retrievalSettings.top_k * 5} · RRF{" "}
                {retrievalSettings.rrf_constant} · {retrievalSettings.reranker_strategy.replace(/_/g, " ")}
              </small>
              <small>Metadata badges may be shown even when their boost is off.</small>
            </div>
            <div className="readiness-grid" data-parsed-chunks={readiness?.parsed_chunks ?? 0}>
              <ReadinessPill label="Full-text" item={readiness?.full_text ?? null} />
              <ReadinessPill label="Vector" item={readiness?.vector ?? null} />
              <ReadinessPill label="Local model" item={readiness?.local_model ?? null} />
            </div>
            <div className="chat-defaults-note chat-embedding-note">
              <strong>Embedding for retrieval</strong>
              <small>Configured: {configuredEmbeddingModel}</small>
              <small>Latest vector index: {latestVectorModel}</small>
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
              <span className="muted">Chat model: {activeSession?.model ?? chatDefaultModel}</span>
            </div>
            <div className="chat-defaults-note">
              <strong>New chat default</strong>
              <small>
                {chatDefaultModel} · {activePrompt?.name ?? settings?.prompt.active_chat_prompt_id ?? "active prompt"}
              </small>
              <small>
                Normal chat searches local repository context first with these chat-owned retrieval settings.
              </small>
              <small>Retrieval embedding: {configuredEmbeddingModel}</small>
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
                <p>Questions search local repository context by default and cite stored source chunks.</p>
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
  onCopyToChat,
  onPromoteToDefaults,
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
  onCopyToChat: () => void;
  onPromoteToDefaults: () => void;
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
              <option value="off">Off</option>
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
        <div className="search-effective-settings">
          <div>
            <div className="eyebrow">Effective settings</div>
            <p>
              {apiSearchMode(mode)} · top-{limit} · pool {candidatePoolSize} · RRF {rrfConstant} ·{" "}
              {rerankerStrategy.replace(/_/g, " ")} · boost {metadataBoostLevel}
            </p>
            <small>
              Search Lab changes are experimental until copied to chat or promoted to repository defaults.
            </small>
          </div>
          <div className="row">
            <button className="btn btn-sm" type="button" onClick={onCopyToChat}>
              Copy to chat
            </button>
            <button className="btn btn-sm btn-primary" type="button" onClick={onPromoteToDefaults}>
              Promote defaults
            </button>
          </div>
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
      {result.score_breakdown.metadata_boost_dimensions && (
        <div className="metadata-boost-breakdown">
          {Object.entries(result.score_breakdown.metadata_boost_dimensions).map(([key, dimension]) => (
            <span className="badge" key={key}>
              {key.replace(/_/g, " ")} {dimension.level}
              {dimension.matched ? ` +${dimension.score.toFixed(2)}` : " no match"}
              {!dimension.ranking_applied ? " off" : ""}
            </span>
          ))}
        </div>
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

function PageImageStrip({
  images,
  pageCount,
  version,
}: {
  images: PageImage[];
  pageCount: number;
  version: DocumentVersion;
}) {
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
          <span className={ocrPageClassName(version, image.page)}>
            {ocrPageLabel(version, image.page)}
          </span>
        </a>
      ))}
    </div>
  );
}

function OcrPageTextPanel({ version, pages }: { version: DocumentVersion; pages: number[] }) {
  const pageResults = pages
    .map((page) => getOcrPageResult(version, page))
    .filter((result): result is OcrPageResult => result !== null && result.text.trim().length > 0);
  if (pageResults.length === 0) {
    return null;
  }
  return (
    <div className="ocr-page-text-panel">
      {pageResults.map((result) => (
        <div className="ocr-page-text" key={result.page}>
          <div className="muted num">
            page {result.page} OCR
            {result.confidence !== null ? ` · confidence ${Math.round(result.confidence * 100)}%` : ""}
          </div>
          <p>{result.text}</p>
        </div>
      ))}
    </div>
  );
}

function SelectedDocumentCard({
  selectedDocument,
  inspection,
  busy,
  onReprocess,
  onRunOcr,
  onDelete,
}: {
  selectedDocument: DocumentSummary | null;
  inspection: Inspection | null;
  busy: boolean;
  onReprocess: () => void;
  onRunOcr: () => void;
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
        <dd>{parserDisplayLabel(version)}</dd>
        <dt>Parser version</dt>
        <dd>{version.parser_version}</dd>
        <dt>Reprocess</dt>
        <dd>{reprocessStatusLabel(version)}</dd>
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
        <button
          className="btn"
          type="button"
          onClick={onRunOcr}
          disabled={busy || !inspection || version.source_type !== "pdf" || !version.ocr_required}
        >
          Run OCR
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
  const reprocessStatus = getReprocessStatus(version);
  if (reprocessStatus?.status === "stale") {
    return reprocessStatus.message;
  }
  if (reprocessStatus?.status === "source_missing") {
    return reprocessStatus.message;
  }
  const hints = version.metadata.patent_section_hints;
  if (Array.isArray(hints) && hints.length > 0) {
    return `Patent PDF hints: ${hints.join(", ")}`;
  }
  const structureHints = version.metadata.structure_hints;
  if (Array.isArray(structureHints) && structureHints.length > 0) {
    return `Source structure hints: ${structureHints.join(", ")}`;
  }
  if (version.ocr_required) {
    const pendingPages = ocrPendingPages(version);
    return pendingPages.length > 0
      ? `OCR pending for pages ${pendingPages.join(", ")}.`
      : "This document has little extractable text and should be inspected with OCR/page images.";
  }
  if (version.warnings.length > 0) {
    return version.warnings.join(" ");
  }
  return `${parserDisplayLabel(version)} produced inspectable source chunks.`;
}

function parserDisplayLabel(version: DocumentVersion) {
  const parserName = parserNameLabel(version.parser_name);
  const route = parserRouteLabel(version);
  if (!route || route === parserName) {
    return parserName;
  }
  return `${parserName} via ${route}`;
}

function parserNameLabel(name: string) {
  const labels: Record<string, string> = {
    "private-rag-built-in": "Built-in parser",
    built_in_fallback: "Built-in fallback",
    docling: "Docling",
    pdfplumber: "pdfplumber",
    pymupdf: "PyMuPDF",
    pypdf: "pypdf",
    rapidocr: "RapidOCR",
    ocrmypdf_tesseract: "OCRmyPDF + Tesseract",
  };
  return labels[name] ?? name;
}

function parserRouteLabel(version: DocumentVersion) {
  const route = version.metadata.parser_route ?? version.metadata.parser_chain;
  if (!Array.isArray(route)) {
    return "";
  }
  return route
    .filter((item): item is string => typeof item === "string" && item.length > 0)
    .map((item) => parserNameLabel(item))
    .join(" -> ");
}

function getPageOcrRoutes(version: DocumentVersion): PageOcrRoute[] {
  const routes = version.metadata.page_ocr_routes;
  if (!Array.isArray(routes)) {
    return [];
  }
  return routes.flatMap((route): PageOcrRoute[] => {
    if (!route || typeof route !== "object") {
      return [];
    }
    const value = route as Partial<PageOcrRoute>;
    if (
      typeof value.page !== "number" ||
      (value.classification !== "born_digital" &&
        value.classification !== "scanned" &&
        value.classification !== "mixed")
    ) {
      return [];
    }
    return [
      {
        page: value.page,
        classification: value.classification,
        quality_score: typeof value.quality_score === "number" ? value.quality_score : 0,
        needs_ocr: Boolean(value.needs_ocr),
        warnings: Array.isArray(value.warnings)
          ? value.warnings.filter((warning): warning is string => typeof warning === "string")
          : [],
      },
    ];
  });
}

function getPageOcrRoute(version: DocumentVersion, page: number) {
  return getPageOcrRoutes(version).find((route) => route.page === page) ?? null;
}

function ocrPendingPages(version: DocumentVersion) {
  return getPageOcrRoutes(version)
    .filter((route) => route.needs_ocr)
    .map((route) => route.page);
}

function ocrPageLabel(version: DocumentVersion, page: number) {
  const route = getPageOcrRoute(version, page);
  if (!route) {
    return version.ocr_required ? "OCR state missing" : "Native text";
  }
  if (route.needs_ocr) {
    return route.classification === "scanned" ? "OCR pending" : "Mixed · OCR pending";
  }
  if (route.classification === "mixed") {
    return "Mixed · native text";
  }
  return "Native text";
}

function ocrPageClassName(version: DocumentVersion, page: number) {
  const route = getPageOcrRoute(version, page);
  if (route?.needs_ocr || (!route && version.ocr_required)) {
    return "page-ocr page-ocr-pending";
  }
  return "page-ocr";
}

function getOcrPageResults(version: DocumentVersion): OcrPageResult[] {
  const pages = version.metadata.ocr_pages;
  if (!Array.isArray(pages)) {
    return [];
  }
  return pages.flatMap((page): OcrPageResult[] => {
    if (!page || typeof page !== "object") {
      return [];
    }
    const value = page as Partial<OcrPageResult>;
    if (typeof value.page !== "number" || typeof value.text !== "string") {
      return [];
    }
    return [
      {
        page: value.page,
        text: value.text,
        confidence: typeof value.confidence === "number" ? value.confidence : null,
        warnings: Array.isArray(value.warnings)
          ? value.warnings.filter((warning): warning is string => typeof warning === "string")
          : [],
        provider: value.provider && typeof value.provider === "object" ? value.provider : {},
        provenance: value.provenance && typeof value.provenance === "object" ? value.provenance : {},
      },
    ];
  });
}

function getOcrPageResult(version: DocumentVersion, page: number) {
  return getOcrPageResults(version).find((result) => result.page === page) ?? null;
}

function isOcrChunk(chunk: Chunk) {
  return chunk.metadata.ocr_derived === true;
}

function getReprocessStatus(version: DocumentVersion): ReprocessStatus | null {
  const status = version.metadata.reprocess_status;
  if (!status || typeof status !== "object") {
    return null;
  }
  const value = status as Partial<ReprocessStatus>;
  if (
    value.status !== "current" &&
    value.status !== "stale" &&
    value.status !== "source_missing" &&
    value.status !== "unknown"
  ) {
    return null;
  }
  return {
    status: value.status,
    stale: Boolean(value.stale),
    reprocess_available: Boolean(value.reprocess_available),
    message: typeof value.message === "string" ? value.message : "",
    changed_fields: Array.isArray(value.changed_fields)
      ? value.changed_fields.filter((field): field is string => typeof field === "string")
      : [],
  };
}

function reprocessStatusLabel(version: DocumentVersion) {
  const status = getReprocessStatus(version);
  if (!status) {
    return "Reprocess status unknown";
  }
  if (status.status === "stale") {
    return status.changed_fields.length > 0
      ? `Stale: ${status.changed_fields.join(", ")}`
      : "Stale";
  }
  if (status.status === "source_missing") {
    return "Source missing";
  }
  if (status.status === "unknown") {
    return "Status unknown";
  }
  return "Current";
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

async function apiErrorMessage(response: Response, fallback: string) {
  try {
    const payload = (await response.json()) as { detail?: unknown };
    if (typeof payload.detail === "string" && payload.detail.trim()) {
      return payload.detail;
    }
  } catch {
    return fallback;
  }
  return fallback;
}

function errorMessage(error: unknown) {
  return error instanceof Error ? error.message : "unknown error";
}

function shortModelName(model: string) {
  const parts = model.split("/");
  return parts[parts.length - 1] ?? model;
}

function defaultChatRetrievalSettings(): ChatRetrievalSettings {
  return {
    mode: "hybrid",
    top_k: 6,
    candidate_pool_size: null,
    rrf_constant: 60,
    reranker_strategy: "cross_encoder",
    metadata_boosts: {
      section: "medium",
      patent_section: "medium",
      document_kind: "low",
      table_figure: "low",
    },
    filters: {},
  };
}

function normalizeChatRetrievalSettings(settings: Partial<ChatRetrievalSettings>): ChatRetrievalSettings {
  const defaults = defaultChatRetrievalSettings();
  return {
    ...defaults,
    ...settings,
    metadata_boosts: {
      ...defaults.metadata_boosts,
      ...(settings.metadata_boosts ?? {}),
    },
    filters: {
      ...defaults.filters,
      ...(settings.filters ?? {}),
    },
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
      retrieval_settings: normalizeChatRetrievalSettings({
        mode: "full_text",
        top_k: topK,
        reranker_strategy: "none",
      }),
    },
    {
      label: "Vector",
      prompt_version_id: promptVersionId,
      model,
      retrieval_settings: normalizeChatRetrievalSettings({
        mode: "vector",
        top_k: topK,
        reranker_strategy: "none",
      }),
    },
    {
      label: "Hybrid",
      prompt_version_id: promptVersionId,
      model,
      retrieval_settings: normalizeChatRetrievalSettings({
        mode: "hybrid",
        top_k: topK,
        reranker_strategy: "none",
      }),
    },
    {
      label: "Reranked hybrid",
      prompt_version_id: promptVersionId,
      model,
      retrieval_settings: normalizeChatRetrievalSettings({
        mode: "hybrid",
        top_k: topK,
        reranker_strategy: "cross_encoder",
      }),
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

function chatModelRoleLabel(role: ChatModelInfo["role"]) {
  switch (role) {
    case "recommended_default":
      return "recommended default";
    case "balanced_local":
      return "balanced local";
    case "larger_local":
      return "larger local";
    case "reasoning_experimental":
      return "reasoning experimental";
  }
}

function modelSourceLabel(source: ModelCatalogSource) {
  return source === "detected" ? "detected locally" : "project-known";
}

function metadataBoostLabel(key: keyof MetadataBoostSettings) {
  const labels: Record<keyof MetadataBoostSettings, string> = {
    section: "Section boost",
    patent_section: "Patent section boost",
    document_kind: "Document kind boost",
    table_figure: "Table/figure boost",
  };
  return labels[key];
}

function defaultParserCatalog(): ParserCatalogEntry[] {
  return [
    {
      id: "auto",
      label: "Auto parser chain",
      role: "auto",
      supported_as: ["structured", "fallback"],
      notes: "Use the project default local parser chain.",
      setup_hint: null,
      readiness_required: false,
    },
    {
      id: "pymupdf",
      label: "PyMuPDF",
      role: "structured",
      supported_as: ["structured", "fallback"],
      notes: "Fast local PDF text extraction with page-aware output.",
      setup_hint: null,
      readiness_required: false,
    },
    {
      id: "docling",
      label: "Docling",
      role: "structured",
      supported_as: ["structured", "fallback"],
      notes: "Structured scientific PDF parsing for richer layout metadata.",
      setup_hint: null,
      readiness_required: true,
    },
    {
      id: "pdfplumber",
      label: "pdfplumber",
      role: "structured",
      supported_as: ["structured", "fallback"],
      notes: "Backlog table/layout parser for born-digital PDFs.",
      setup_hint: null,
      readiness_required: true,
    },
    {
      id: "pypdf",
      label: "pypdf",
      role: "fallback",
      supported_as: ["structured", "fallback"],
      notes: "Conservative local PDF text-layer parser.",
      setup_hint: null,
      readiness_required: false,
    },
    {
      id: "built_in_fallback",
      label: "Built-in fallback",
      role: "fallback",
      supported_as: ["structured", "fallback"],
      notes: "Minimal built-in fallback when optional parsers cannot recover text.",
      setup_hint: null,
      readiness_required: false,
    },
    {
      id: "needs_ocr",
      label: "Needs OCR gate",
      role: "ocr_gate",
      supported_as: ["fallback"],
      notes: "Marks image-only or low-text PDFs for OCR inspection.",
      setup_hint: null,
      readiness_required: false,
    },
    {
      id: "ocrmypdf_tesseract",
      label: "OCRmyPDF + Tesseract",
      role: "ocr_provider",
      supported_as: ["fallback"],
      notes: "Planned local OCR provider for scanned/image-heavy PDF pages.",
      setup_hint: "Install OCRmyPDF and Tesseract locally.",
      readiness_required: true,
    },
    {
      id: "rapidocr",
      label: "RapidOCR",
      role: "ocr_provider",
      supported_as: ["fallback"],
      notes: "Planned optional OCR fallback when baseline OCR quality is poor.",
      setup_hint: "Install RapidOCR locally for OCR fallback evaluation.",
      readiness_required: true,
    },
  ];
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
    {
      label: "retrieval",
      value: `${settings.retrieval.mode} top-${settings.retrieval.top_k} / ${settings.retrieval.reranker_strategy}`,
    },
    { label: "chunking", value: `${settings.chunking.mode} ${settings.chunking.chunk_size}/${settings.chunking.chunk_overlap}` },
    { label: "full-text", value: settings.full_text.tokenizer },
    { label: "parser", value: settings.parser.structured_parser },
  ];
}

function cloneSettings(settings: RepositorySettings | null) {
  return settings ? (JSON.parse(JSON.stringify(settings)) as RepositorySettings) : null;
}

type SettingsValidationIssue = {
  field: string;
  message: string;
};

function validateSettingsDraft(
  settings: RepositorySettings | null,
  modelCatalog: RepositoryModelCatalog | null = null,
): SettingsValidationIssue[] {
  if (!settings) {
    return [{ field: "settings", message: "Settings are unavailable." }];
  }
  const issues: SettingsValidationIssue[] = [];
  const knownEmbeddingModel = modelCatalog?.embedding_models.find(
    (model) => model.provider === settings.embedding.provider && model.model === settings.embedding.model,
  );
  const parserCatalog = modelCatalog?.parser_choices ?? defaultParserCatalog();
  const structuredParserChoices = parserCatalog.filter((entry) =>
    entry.supported_as.includes("structured"),
  );
  const fallbackParserChoices = parserCatalog.filter((entry) =>
    entry.supported_as.includes("fallback"),
  );
  if (settings.chunking.chunk_size < 100 || settings.chunking.chunk_size > 8000) {
    issues.push({ field: "chunking.chunk_size", message: "Chunk size must be between 100 and 8000." });
  }
  if (settings.chunking.chunk_overlap < 0) {
    issues.push({ field: "chunking.chunk_overlap", message: "Chunk overlap cannot be negative." });
  }
  if (settings.chunking.chunk_overlap >= settings.chunking.chunk_size) {
    issues.push({ field: "chunking.chunk_overlap", message: "Chunk overlap must be smaller than chunk size." });
  }
  if (!settings.parser.structured_parser.trim()) {
    issues.push({ field: "parser.structured_parser", message: "Structured parser is required." });
  } else if (!structuredParserChoices.some((entry) => entry.id === settings.parser.structured_parser)) {
    issues.push({ field: "parser.structured_parser", message: "Choose a supported structured parser." });
  }
  if (!settings.parser.fallback_parser.trim()) {
    issues.push({ field: "parser.fallback_parser", message: "Fallback parser is required." });
  } else if (!fallbackParserChoices.some((entry) => entry.id === settings.parser.fallback_parser)) {
    issues.push({ field: "parser.fallback_parser", message: "Choose a supported fallback parser." });
  }
  if (settings.ocr.fallback_enabled && settings.ocr.fallback_provider === settings.ocr.provider) {
    issues.push({ field: "ocr.fallback_provider", message: "OCR fallback must differ from primary provider." });
  }
  if (!settings.ocr.language.trim()) {
    issues.push({ field: "ocr.language", message: "OCR language is required." });
  }
  if (settings.ocr.confidence_threshold < 0 || settings.ocr.confidence_threshold > 1) {
    issues.push({ field: "ocr.confidence_threshold", message: "OCR confidence threshold must be between 0 and 1." });
  }
  if (settings.ocr.min_text_length < 0) {
    issues.push({ field: "ocr.min_text_length", message: "OCR minimum text cannot be negative." });
  }
  if (settings.ocr.max_pages < 1) {
    issues.push({ field: "ocr.max_pages", message: "OCR max pages must be at least 1." });
  }
  if (!settings.embedding.model.trim()) {
    issues.push({ field: "embedding.model", message: "Embedding model is required." });
  }
  if (!settings.vector.collection_name.trim()) {
    issues.push({ field: "vector.collection_name", message: "Qdrant collection is required." });
  }
  if (settings.vector.vector_size < 1) {
    issues.push({ field: "vector.vector_size", message: "Vector size must be at least 1." });
  }
  if (knownEmbeddingModel && settings.vector.vector_size !== knownEmbeddingModel.vector_size) {
    issues.push({
      field: "vector.vector_size",
      message: `${knownEmbeddingModel.label} requires ${knownEmbeddingModel.vector_size} dimensions.`,
    });
  }
  if (knownEmbeddingModel && !knownEmbeddingModel.supported_distances.includes(settings.vector.distance)) {
    issues.push({
      field: "vector.distance",
      message: `${knownEmbeddingModel.label} supports ${knownEmbeddingModel.supported_distances.join(", ")} distance.`,
    });
  }
  if (!knownEmbeddingModel && settings.embedding.provider === "ollama" && settings.vector.distance !== "cosine") {
    issues.push({ field: "vector.distance", message: "Ollama embeddings currently require cosine distance." });
  }
  if (settings.reranking.strategy === "cross_encoder" && !settings.reranking.model?.trim()) {
    issues.push({ field: "reranking.model", message: "Cross-encoder reranking requires a model." });
  }
  if (settings.retrieval.top_k < 1 || settings.retrieval.top_k > 50) {
    issues.push({ field: "retrieval.top_k", message: "Retrieval top-k must be between 1 and 50." });
  }
  if (
    settings.retrieval.candidate_pool_size != null &&
    (settings.retrieval.candidate_pool_size < 1 || settings.retrieval.candidate_pool_size > 250)
  ) {
    issues.push({ field: "retrieval.candidate_pool_size", message: "Candidate pool must be between 1 and 250." });
  }
  if (settings.retrieval.rrf_constant < 1 || settings.retrieval.rrf_constant > 1000) {
    issues.push({ field: "retrieval.rrf_constant", message: "RRF constant must be between 1 and 1000." });
  }
  if (!settings.model.ollama_chat_model.trim()) {
    issues.push({ field: "model.ollama_chat_model", message: "Chat model is required." });
  }
  if (!settings.prompt.library.some((prompt) => prompt.id === settings.prompt.active_chat_prompt_id)) {
    issues.push({ field: "prompt.active_chat_prompt_id", message: "Active chat prompt must exist in the prompt library." });
  }
  for (const prompt of settings.prompt.library) {
    if (!prompt.name.trim()) {
      issues.push({ field: `prompt.library.${prompt.id}.name`, message: "Prompt names are required." });
    }
    if (!prompt.text.trim()) {
      issues.push({ field: `prompt.library.${prompt.id}.text`, message: "Prompt text is required." });
    }
  }
  return issues;
}

function settingsReadinessItems(
  readiness: SettingsReadinessResponse | null,
  settings: RepositorySettings,
): SettingsReadinessItem[] {
  if (readiness) {
    return readiness.items;
  }
  return [
    {
      target: "qdrant",
      label: "Qdrant",
      status: "not_checked",
      ready: false,
      message: "Run an explicit check before relying on vector rebuild or search.",
      model: settings.vector.collection_name,
    },
    {
      target: "chat",
      label: "Chat model",
      status: "not_checked",
      ready: false,
      message: "Run an explicit check before starting model-backed chat.",
      model: settings.model.ollama_chat_model,
    },
    {
      target: "embedding",
      label: "Embedding model",
      status: "not_checked",
      ready: false,
      message: "Run an explicit check before rebuilding embeddings.",
      model: settings.embedding.model,
    },
    {
      target: "reranker",
      label: "Reranker",
      status: "not_checked",
      ready: false,
      message:
        settings.reranking.strategy === "none"
          ? "Reranking is disabled; the explicit check will mark this as skipped."
          : "Run an explicit check before using cross-encoder reranking.",
      model: settings.reranking.model ?? settings.reranking.strategy,
    },
  ];
}

function dashboardReadinessItems(
  summary: DashboardSummary | null,
  settings: RepositorySettings | null,
): SettingsReadinessItem[] {
  if (summary) {
    return summary.settings_readiness.items;
  }
  if (settings) {
    return settingsReadinessItems(null, settings);
  }
  return [
    {
      target: "qdrant",
      label: "Qdrant",
      status: "not_checked",
      ready: false,
      message: "Repository summary has not loaded yet.",
      model: null,
    },
    {
      target: "chat",
      label: "Chat model",
      status: "not_checked",
      ready: false,
      message: "Repository summary has not loaded yet.",
      model: null,
    },
    {
      target: "embedding",
      label: "Embedding model",
      status: "not_checked",
      ready: false,
      message: "Repository summary has not loaded yet.",
      model: null,
    },
    {
      target: "reranker",
      label: "Reranker",
      status: "not_checked",
      ready: false,
      message: "Repository summary has not loaded yet.",
      model: null,
    },
  ];
}

function dashboardConfigRows(summary: DashboardSummary | null, settings: RepositorySettings | null) {
  if (summary) {
    const config = summary.active_config;
    return [
      { label: "chunking", value: `${config.chunking.mode} ${config.chunking.chunk_size}/${config.chunking.chunk_overlap}` },
      { label: "embedding", value: `${config.embedding.provider} / ${config.embedding.model}` },
      { label: "vector", value: `${config.vector.collection_name} · ${config.vector.vector_size} · ${config.vector.distance}` },
      {
        label: "reranking",
        value: config.reranking.model
          ? `${config.reranking.strategy} / ${config.reranking.model}`
          : config.reranking.strategy,
      },
      { label: "full-text", value: `${config.full_text.tokenizer} · prefix ${formatBoolean(config.full_text.prefix_index)}` },
      { label: "chat", value: config.chat_model },
      { label: "active prompt", value: config.active_chat_prompt_name },
    ];
  }
  return settingsSummaryRows(settings).filter((row) => row.label !== "parser");
}

function dashboardIndexStatusLabel(status: DashboardIndexStatus) {
  const labels: Record<DashboardIndexStatus, string> = {
    ready: "Ready",
    missing: "Missing",
    partial: "Partial",
    stale: "Stale",
  };
  return labels[status];
}

function adminStorageStatusLabel(status: RepositoryAdminStorageHint["status"]) {
  const labels: Record<RepositoryAdminStorageHint["status"], string> = {
    tracked: "tracked",
    present: "present",
    not_found: "not found",
    preserved: "preserved",
    out_of_scope: "out of scope",
  };
  return labels[status];
}

function adminCleanupActionLabel(action: RepositoryCleanupAction) {
  const labels: Record<RepositoryCleanupAction, string> = {
    remove: "Would remove",
    preserve: "Preserved",
    skip: "Skipped",
    retry_required: "Retry needed",
  };
  return labels[action];
}

function adminCleanupCategoryLabel(category: RepositoryAdminStorageHint["category"]) {
  return category.replace(/_/g, " ");
}

function repositoryDeleteStatusLabel(status: RepositoryDeleteResult["status"]) {
  const labels: Record<RepositoryDeleteResult["status"], string> = {
    completed: "completed",
    completed_with_warnings: "completed with warnings",
    failed: "failed",
  };
  return labels[status];
}

function dashboardQuickActions() {
  return [
    { view: "documents" as const, label: "Document Manager" },
    { view: "search" as const, label: "Search Lab" },
    { view: "chat" as const, label: "Chat Workspace" },
    { view: "sandbox" as const, label: "Prompt Sandbox" },
    { view: "export" as const, label: "Export Center" },
    { view: "recreate" as const, label: "Recreate Repository" },
    { view: "settings" as const, label: "Settings / Models" },
  ];
}

function dashboardActivityKindLabel(kind: DashboardActivityItem["kind"]) {
  const labels: Record<DashboardActivityItem["kind"], string> = {
    document: "Document",
    retrieval: "Retrieval",
    chat: "Chat",
    sandbox: "Sandbox",
    export: "Export",
    recreate: "Recreate",
  };
  return labels[kind];
}

function settingsReadinessStatusLabel(status: SettingsReadinessStatus) {
  const labels: Record<SettingsReadinessStatus, string> = {
    not_checked: "Not checked",
    unavailable_runtime: "Runtime unavailable",
    not_installed: "Not installed",
    ready: "Ready",
    failed: "Failed",
    skipped: "Skipped",
  };
  return labels[status];
}

function workflowLinksForImpact(item: SettingsImpact) {
  const links: Array<{ view: View; label: string }> = [];
  const add = (view: View, label: string) => {
    if (!links.some((link) => link.view === view)) {
      links.push({ view, label });
    }
  };

  switch (item.category) {
    case "document_reprocessing":
      add("documents", "Open Document Manager");
      break;
    case "full_text_rebuild":
    case "vector_rebuild":
    case "retrieval_defaults":
    case "evaluation_freshness":
      add("search", "Open Search Lab");
      break;
    case "chat_defaults":
      add("chat", "Open Chat Workspace");
      break;
    case "prompt_defaults":
      add("chat", "Open Chat Workspace");
      add("sandbox", "Open Prompt Sandbox");
      break;
    case "export_recreate":
      add("export", "Open Export Center");
      add("recreate", "Open Recreate Repository");
      break;
  }

  return links;
}

function workflowLinksForReadiness(item: SettingsReadinessItem) {
  if (item.status === "ready" || item.status === "skipped" || item.status === "not_checked") {
    return [];
  }
  if (item.target === "chat") {
    return [{ view: "chat" as const, label: "Open Chat Workspace" }];
  }
  return [{ view: "search" as const, label: "Open Search Lab" }];
}

function dashboardWarningLinks(warning: string) {
  const lower = warning.toLowerCase();
  const links: Array<{ view: View; label: string }> = [];
  const add = (view: View, label: string) => {
    if (!links.some((link) => link.view === view)) {
      links.push({ view, label });
    }
  };

  if (
    lower.includes("full-text") ||
    lower.includes("vector") ||
    lower.includes("embedding") ||
    lower.includes("qdrant")
  ) {
    add("search", "Open Search Lab");
  }
  if (lower.includes("chat") || lower.includes("model")) {
    add("chat", "Open Chat Workspace");
  }
  if (lower.includes("document") || lower.includes("chunk")) {
    add("documents", "Open Document Manager");
  }
  if (lower.includes("source") || lower.includes("bundle") || lower.includes("recreate")) {
    add("recreate", "Open Recreate Repository");
  }
  add("settings", "Open Settings / Models");
  return links;
}

function formatBoolean(value: boolean | undefined) {
  if (value === undefined) {
    return "unavailable";
  }
  return value ? "enabled" : "disabled";
}

async function settingsSaveErrorMessage(response: Response) {
  try {
    const payload = await response.json();
    if (Array.isArray(payload.detail)) {
      return payload.detail
        .map((detail: { msg?: string; loc?: string[] }) => detail.msg ?? detail.loc?.join(".") ?? "Invalid settings")
        .join(" ");
    }
    if (typeof payload.detail === "string") {
      return payload.detail;
    }
  } catch {
    // Fall through to a generic message when the backend response is not JSON.
  }
  return "Settings save failed";
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

function hashForView(view: View) {
  switch (view) {
    case "dashboard":
      return "repository-dashboard";
    case "documents":
      return "documents";
    case "source":
      return "source-viewer";
    case "chat":
      return "chat-workspace";
    case "sandbox":
      return "prompt-sandbox";
    case "settings":
      return "settings-models";
    case "admin":
      return "repository-administration";
    case "export":
      return "export-center";
    case "recreate":
      return "recreate-repository";
    case "search":
      return "search-lab";
  }
}

function viewFromHash(hash: string): View {
  if (hash === "" || hash === "#" || hash === "#home" || hash === "#repository-dashboard") {
    return "dashboard";
  }
  if (hash === "#recreate-repository") {
    return "recreate";
  }
  if (hash === "#export-center") {
    return "export";
  }
  if (hash === "#settings-models") {
    return "settings";
  }
  if (hash === "#repository-administration" || hash === "#admin") {
    return "admin";
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
