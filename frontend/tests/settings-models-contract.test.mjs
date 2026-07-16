import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("Settings / Models is a first-class routed view", () => {
  assert.match(source, /type View =[\s\S]*?"dashboard"[\s\S]*?"documents"[\s\S]*?"source"[\s\S]*?"search"[\s\S]*?"sandbox"[\s\S]*?"chat"[\s\S]*?"settings"[\s\S]*?"export"[\s\S]*?"recreate"/);
  assert.match(source, /#settings-models/);
  assert.match(source, /navigateTo\("settings"\)/);
  assert.match(source, /activeView === "settings"/);
  assert.match(source, /function SettingsModels/);
  assert.match(source, /Settings \/ Models/);
});

test("Settings / Models shows repository-scoped grouped defaults", () => {
  assert.match(source, /Repository settings/);
  assert.match(source, /repository\?\.[\s\S]*?name/);
  assert.match(source, /Chunking and parser/);
  assert.match(source, /Full-text/);
  assert.match(source, /Vector and embedding/);
  assert.match(source, /Reranking/);
  assert.match(source, /Chat defaults/);
  assert.match(source, /chatModelRegistry/);
  assert.match(source, /Known Ollama model/);
  assert.match(source, /Custom local Ollama model/);
  assert.match(source, /settings-known-chat-model/);
  assert.match(source, /settings-model-guidance/);
  assert.match(source, /Export defaults/);
  assert.match(source, /draft\.chunking\.chunk_size/);
  assert.match(source, /draft\.export\.include_sources/);
});

test("Settings / Models exposes required models and readiness placeholders", () => {
  assert.match(source, /Model readiness/);
  assert.match(source, /Configured local models/);
  assert.match(source, /Check readiness/);
  assert.match(source, /function checkRepositorySettingsReadiness/);
  assert.match(source, /settings\/readiness/);
  assert.match(source, /chat\/models/);
  assert.match(source, /type ChatModelRegistry/);
  assert.match(source, /ReadinessCard/);
  assert.match(source, /Qdrant/);
  assert.match(source, /Embedding/);
  assert.match(source, /Reranker/);
  assert.match(source, /requiredModelsForSettings\(draft\)/);
  assert.match(source, /Not checked/);
  assert.match(source, /Runtime unavailable/);
  assert.match(source, /Not installed/);
  assert.match(source, /Skipped/);
  assert.match(styles, /\.settings-readiness-ready/);
  assert.match(styles, /\.settings-readiness-unavailable_runtime/);
  assert.match(styles, /\.settings-readiness-not_installed/);
});

test("Settings / Models supports edit, save, cancel, and field validation", () => {
  assert.match(source, /function saveRepositorySettings/);
  assert.match(source, /method: "PUT"/);
  assert.match(source, /JSON\.stringify\(\{ settings: nextSettings \}\)/);
  assert.match(source, /Save settings/);
  assert.match(source, /Cancel/);
  assert.match(source, /validateSettingsDraft/);
  assert.match(source, /Chunk overlap must be smaller than chunk size/);
  assert.match(source, /Ollama embeddings currently require cosine distance/);
  assert.match(source, /Cross-encoder reranking requires a model/);
  assert.match(styles, /\.settings-field-error/);
});

test("Settings / Models previews and preserves settings impact", () => {
  assert.match(source, /function previewRepositorySettingsImpact/);
  assert.match(source, /settings\/impact/);
  assert.match(source, /SettingsImpactResponse/);
  assert.match(source, /pendingImpact/);
  assert.match(source, /lastSavedImpact/);
  assert.match(source, /SettingsImpactPanel/);
  assert.match(source, /Pending impact/);
  assert.match(source, /Saved impact/);
  assert.match(source, /document_reprocessing/);
  assert.match(source, /full_text_rebuild/);
  assert.match(source, /vector_rebuild/);
  assert.match(styles, /\.settings-impact/);
  assert.match(styles, /\.settings-impact-list/);
});

test("Settings / Models manages normal chat prompt library entries", () => {
  assert.match(source, /Chat prompt library/);
  assert.match(source, /Add prompt/);
  assert.match(source, /removePromptEntry/);
  assert.match(source, /active_chat_prompt_id/);
  assert.match(source, /Prompt names are required/);
  assert.match(source, /Prompt text is required/);
  assert.match(styles, /\.settings-prompts/);
  assert.match(styles, /\.settings-prompt-list/);
});

test("Settings / Models links back to workflow-owned pages", () => {
  assert.match(source, /onNavigate\("documents"\)/);
  assert.match(source, /onNavigate\("search"\)/);
  assert.match(source, /onNavigate\("chat"\)/);
  assert.match(source, /onNavigate\("sandbox"\)/);
  assert.match(source, /onNavigate\("export"\)/);
  assert.match(source, /workflowLinksForImpact/);
  assert.match(source, /workflowLinksForReadiness/);
  assert.match(source, /Open Document Manager/);
  assert.match(source, /Open Search Lab/);
  assert.match(source, /Open Chat Workspace/);
  assert.match(source, /Open Prompt Sandbox/);
  assert.match(source, /Open Export Center/);
  assert.match(source, /Open Recreate Repository/);
  assert.match(styles, /\.settings-impact-actions/);
  assert.match(styles, /\.settings-readiness-actions/);
  assert.match(styles, /\.settings-layout/);
  assert.match(styles, /\.settings-grid/);
  assert.match(styles, /\.settings-readiness-grid/);
});

test("Settings defaults propagate to chat and export without removing per-run overrides", () => {
  assert.match(source, /<ChatWorkspace[\s\S]*?settings=\{repositorySettings\}/);
  assert.match(source, /New chat default/);
  assert.match(source, /settings\?\.model\.ollama_chat_model/);
  assert.match(source, /activePrompt\?\.name/);
  assert.match(source, /activeSession\?\.model \?\? chatDefaultModel/);
  assert.match(source, /defaultIncludeSources=\{repositorySettings\?\.export\.include_sources \?\? true\}/);
  assert.match(source, /defaultIncludeIndexes=\{repositorySettings\?\.export\.include_indexes \?\? false\}/);
  assert.match(source, /Saved export defaults/);
  assert.match(source, /sandbox remains per export/);
  assert.match(source, /onRerankerStrategyChange=\{setRerankerStrategy\}/);
  assert.match(source, /onRetrievalSettingsChange=\{setChatRetrievalSettings\}/);
  assert.match(source, /sandboxComparisonRunConfigs\(selectedPrompt\.id, sandboxModel, sandboxTopK\)/);
  assert.match(styles, /\.chat-defaults-note/);
  assert.match(styles, /\.export-default-note/);
});
