import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");

test("Chat Workspace is a first-class routed view", () => {
  assert.match(source, /type View = "documents" \| "source" \| "search" \| "chat"/);
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
  assert.match(source, /sessions\/\$\{chatSession\.id\}\/messages/);
  assert.match(source, /loadChatSessions/);
  assert.match(source, /createChatSession/);
  assert.match(source, /askChatQuestion/);
  assert.match(source, /retrieval_settings: chatRetrievalSettings/);
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

test("Chat Workspace exposes retrieval readiness and explicit rebuild controls", () => {
  assert.match(source, /chat\/readiness/);
  assert.match(source, /ReadinessPill/);
  assert.match(source, /Rebuild full-text/);
  assert.match(source, /Rebuild vector/);
  assert.match(source, /chat-mode/);
  assert.match(source, /chat-reranker/);
  assert.match(source, /chat-top-k/);
});

test("Chat Workspace supports thinking state and session deletion", () => {
  assert.match(source, /Local LLM is thinking/);
  assert.match(source, /thinking-dots/);
  assert.match(source, /deleteChatSession/);
  assert.match(source, /clearChatSessions/);
  assert.match(source, /Clear all/);
});
