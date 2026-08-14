import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");

test("Chat Workspace is a first-class routed view", () => {
  assert.match(source, /type View =[\s\S]*?"dashboard"[\s\S]*?"documents"[\s\S]*?"source"[\s\S]*?"search"[\s\S]*?"sandbox"[\s\S]*?"chat"[\s\S]*?"settings"[\s\S]*?"export"[\s\S]*?"recreate"/);
  assert.match(source, /#chat-workspace/);
  assert.match(source, /navigateTo\("chat"\)/);
  assert.match(source, /activeView === "chat"/);
  assert.match(source, /Chat Workspace/);
});

test("Chat Workspace uses persisted backend chat sessions and messages", () => {
  assert.match(source, /type ChatSession =/);
  assert.match(source, /type ChatMessage =/);
  assert.match(source, /type ChatRetrievalSettings =/);
  assert.match(source, /chat\/sessions/);
  assert.match(source, /loadChatSession/);
  assert.match(source, /chat\/sessions\/\$\{chatSessionId\}/);
  assert.match(source, /setChatSessions\(\(current\) =>[\s\S]*payload\.id \? payload : session/);
  assert.match(source, /sessions\/\$\{chatSession\.id\}\/messages/);
  assert.match(source, /loadChatSessions/);
  assert.match(source, /createChatSession/);
  assert.match(source, /askChatQuestion/);
  assert.match(source, /retrieval_settings: chatRetrievalSettings/);
});

test("Chat Workspace supports renaming sessions without reloading the list", async () => {
  const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

  assert.match(source, /renameChatSession/);
  assert.match(source, /method: "PATCH"/);
  assert.match(source, /JSON\.stringify\(\{ title: nextTitle \}\)/);
  assert.match(source, /setChatSessions\(\(current\) =>[\s\S]*session\.id === payload\.id \? payload : session/);
  assert.match(source, /setChatMessage\("Chat session renamed"\)/);
  assert.match(source, /Chat title is required/);
  assert.match(source, /function ChatSessionListItem/);
  assert.match(source, /onStartRename/);
  assert.match(source, /onSaveRename/);
  assert.match(source, /Session title/);
  assert.match(source, /aria-label=\{`Rename \$\{session\.title\}`\}/);
  assert.doesNotMatch(source, /title: "Repository chat"/);
  assert.match(styles, /\.session-rename/);
  assert.match(styles, /\.session-item-editing/);
  assert.match(styles, /\.session-edit-actions/);
});

test("Chat Workspace renders citation cards and source navigation", () => {
  assert.match(source, /type ChatCitation =/);
  assert.match(source, /activeCitation/);
  assert.match(source, /Citation \{activeCitation\.token\}/);
  assert.match(source, /Open in Source Viewer/);
  assert.match(source, /function openChatCitation/);
  assert.match(source, /setSelectedDocumentId\(citation\.document_id\)/);
  assert.match(source, /setPendingSourceTarget/);
  assert.match(source, /citationProvenanceLabel/);
  assert.match(source, /text_preview/);
});

test("Chat Workspace exposes draft and persisted context inspection", () => {
  assert.match(source, /type ChatContextInspection =/);
  assert.match(source, /context_inspection_available: boolean/);
  assert.match(source, /contextInspector/);
  assert.match(source, /previewChatContext/);
  assert.match(source, /inspectChatMessage/);
  assert.match(source, /chat\/sessions\/\$\{chatSession\.id\}\/context-preview/);
  assert.match(source, /messages\/\$\{chatMessageId\}\/context/);
  assert.match(source, /Inspect context/);
  assert.match(source, /message\.context_inspection_available/);
  assert.match(source, /Context inspector/);
  assert.match(source, /Retrieved context/);
  assert.match(source, /Assembled messages/);
  assert.match(source, /No retrieved context entries were assembled for this turn/);
  assert.match(source, /context_text\?: string \| null/);
  assert.match(source, /expandedContextIds/);
  assert.match(source, /toggleContextEntry/);
  assert.match(source, /Expand context/);
  assert.match(source, /Collapse context/);
  assert.match(source, /context-entry-full/);
  assert.match(source, /Open source/);
  assert.match(source, /function openChatContextEntry/);
  assert.match(source, /setPendingSourceTarget\(\{ documentId: result\.document_id, chunkId: result\.chunk_id \}\)/);
});

test("Chat Workspace exposes retrieval readiness and explicit rebuild controls", () => {
  assert.match(source, /chat\/readiness/);
  assert.match(source, /parsed_chunks/);
  assert.match(source, /ReadinessPill/);
  assert.match(source, /chatReadyForSelectedMode/);
  assert.match(source, /Repository context not ready/);
  assert.match(source, /data-readiness-status=\{status\}/);
  assert.match(source, /status === "partial"/);
  assert.match(source, /status === "stale"/);
  assert.match(source, /throw new Error\(await apiErrorMessage\(response, "readiness unavailable"\)\)/);
  assert.match(source, /apiErrorMessage\(response, "rebuild failed"\)/);
  assert.match(source, /\$\{kind\} rebuild failed: \$\{errorMessage\(error\)\}/);
  assert.match(source, /Rebuild full-text/);
  assert.match(source, /Rebuild vector/);
  assert.match(source, /chat-mode/);
  assert.match(source, /chat-reranker/);
  assert.match(source, /chat-top-k/);
  assert.match(source, /chat-candidate-pool/);
  assert.match(source, /chat-rrf/);
  assert.match(source, /chat-filter-document-kind/);
  assert.match(source, /chat-boost-\$\{key\}/);
  assert.match(source, /Effective retrieval/);
  assert.match(source, /Metadata badges may be shown even when their boost is off/);
  assert.match(source, /Last checked/);
  assert.match(source, /Checking indexes and local model/);
  assert.match(source, /searches local repository context first/);
  assert.match(source, /Embedding for retrieval/);
  assert.match(source, /Configured: \{configuredEmbeddingModel\}/);
  assert.match(source, /Latest vector index: \{latestVectorModel\}/);
  assert.match(source, /Retrieval embedding: \{configuredEmbeddingModel\}/);
  assert.doesNotMatch(source, /settings are saved on send/);
});

test("Chat Workspace offers stale parser chunk repair through repository reprocess", async () => {
  const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

  assert.match(source, /function repairChatStaleDocuments/);
  assert.match(source, /documents\/batch\/reprocess/);
  assert.match(source, /all_repository_documents: true/);
  assert.match(source, /isParserChunkStaleMessage\(message\)/);
  assert.match(source, /contextInspectorMessage && isParserChunkStaleMessage\(contextInspectorMessage\)/);
  assert.match(source, /throw new Error\(await apiErrorMessage\(response, "chat question failed"\)\)/);
  assert.match(source, /throw new Error\(await apiErrorMessage\(response, "context preview failed"\)\)/);
  assert.match(source, /Reprocess repository documents/);
  assert.match(source, /Chat Workspace reprocess complete/);
  assert.match(source, /chatStaleRepairSummary/);
  assert.match(source, /counts\.completed/);
  assert.match(source, /counts\.skipped/);
  assert.match(source, /counts\.failed/);
  assert.match(source, /counts\.missing_source/);
  assert.match(source, /await loadDocuments\(repository\.id\)/);
  assert.match(source, /await loadDashboardSummary\(repository\.id\)/);
  assert.match(source, /await loadChatReadiness\(repository\.id, false\)/);
  assert.match(source, /setLastRebuild\(null\)/);
  assert.match(source, /Full-text and vector rebuild controls remain explicit after reprocess/);
  assert.match(styles, /\.chat-stale-repair/);
  assert.match(styles, /\.chat-stale-repair-summary/);
});

test("Chat Workspace supports thinking state and session deletion", () => {
  assert.match(source, /Local LLM is thinking/);
  assert.match(source, /Local model is still working/);
  assert.match(source, /thinking-dots/);
  assert.match(source, /deleteChatSession/);
  assert.match(source, /clearChatSessions/);
  assert.match(source, /Clear all/);
});

test("Chat Workspace lets the composer hug chat output until scrolling is needed", async () => {
  const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

  assert.match(source, /useRef/);
  assert.match(source, /threadRef/);
  assert.match(source, /chat-composer/);
  assert.match(source, /chat-thread chat-thread-empty/);
  assert.match(styles, /\.chat-thread[\s\S]*overflow-y: auto/);
  assert.match(styles, /\.chat-main[\s\S]*flex-direction: column/);
  assert.match(styles, /\.chat-main[\s\S]*max-height: calc\(100vh - 132px\)/);
  assert.match(styles, /\.chat-main[\s\S]*overflow: hidden/);
  assert.match(styles, /\.chat-thread[\s\S]*min-height: 0/);
  assert.match(styles, /\.chat-thread[\s\S]*flex: 0 1 auto/);
  assert.match(styles, /\.chat-thread-empty[\s\S]*flex: 0 0 auto/);
  assert.match(styles, /\.chat-composer/);
});

test("Chat Workspace submits on Enter and keeps Shift Enter for new lines", () => {
  assert.match(source, /event\.key === "Enter"/);
  assert.match(source, /!event\.shiftKey/);
  assert.match(source, /event\.preventDefault\(\)/);
  assert.match(source, /event\.nativeEvent\.isComposing/);
});

test("Chat retrieval panel lives below sessions in the left column", async () => {
  const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

  assert.match(source, /className="chat-side"[\s\S]*className="card card-pad-sm session-list"[\s\S]*className="card card-pad-sm chat-settings-panel"/);
  assert.match(styles, /\.chat-side[\s\S]*flex-direction: column/);
  assert.match(styles, /\.chat-settings-controls[\s\S]*grid-template-columns: 1fr/);
});
