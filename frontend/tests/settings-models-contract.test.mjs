import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("Settings / Models is a first-class routed view", () => {
  assert.match(source, /type View = "documents" \| "source" \| "search" \| "sandbox" \| "chat" \| "settings" \| "export" \| "recreate"/);
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
  assert.match(source, /Export defaults/);
  assert.match(source, /settings\?\.chunking\.chunk_size/);
  assert.match(source, /settings\?\.export\.include_sources/);
});

test("Settings / Models exposes required models and readiness placeholders", () => {
  assert.match(source, /Model readiness/);
  assert.match(source, /Configured local models/);
  assert.match(source, /ReadinessPlaceholder/);
  assert.match(source, /Qdrant/);
  assert.match(source, /Embedding/);
  assert.match(source, /Reranker/);
  assert.match(source, /requiredModelsForSettings\(settings\)/);
  assert.match(source, /Not checked/);
});

test("Settings / Models links back to workflow-owned pages", () => {
  assert.match(source, /onNavigate\("documents"\)/);
  assert.match(source, /onNavigate\("search"\)/);
  assert.match(source, /onNavigate\("chat"\)/);
  assert.match(source, /onNavigate\("sandbox"\)/);
  assert.match(source, /onNavigate\("export"\)/);
  assert.match(styles, /\.settings-layout/);
  assert.match(styles, /\.settings-grid/);
  assert.match(styles, /\.settings-readiness-grid/);
});
