import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("Export Center is a first-class routed view", () => {
  assert.match(source, /type View = "documents" \| "source" \| "search" \| "sandbox" \| "chat" \| "export" \| "recreate"/);
  assert.match(source, /#export-center/);
  assert.match(source, /navigateTo\("export"\)/);
  assert.match(source, /activeView === "export"/);
  assert.match(source, /function ExportCenter/);
  assert.match(source, /Export Center/);
});

test("Export Center exposes PRD9 bundle options and defaults", () => {
  assert.match(source, /const \[exportIncludeSources, setExportIncludeSources\] = useState\(true\)/);
  assert.match(source, /const \[exportIncludeSandbox, setExportIncludeSandbox\] = useState\(false\)/);
  assert.match(source, /setExportIncludeSources\(payload\.settings\.export\.include_sources\)/);
  assert.match(source, /export-include-sources/);
  assert.match(source, /export-include-sandbox/);
  assert.match(source, /Include source files/);
  assert.match(source, /Include sandbox runs\/comparisons/);
  assert.match(source, /Default export excludes sandbox runs/);
});

test("Export Center calls the backend bundle export and creates a ZIP download", () => {
  assert.match(source, /function exportRepositoryBundle/);
  assert.match(source, /exports\/bundle\?\$\{params\}/);
  assert.match(source, /include_sources: String\(exportIncludeSources\)/);
  assert.match(source, /include_sandbox: String\(exportIncludeSandbox\)/);
  assert.match(source, /method: "POST"/);
  assert.match(source, /response\.blob\(\)/);
  assert.match(source, /filenameFromContentDisposition/);
  assert.match(source, /URL\.createObjectURL\(blob\)/);
  assert.match(source, /download=\{filename \?\? "repository-export\.zip"\}/);
  assert.match(source, /Export failed/);
});

test("Export Center shows counts, settings, and manifest summary details", () => {
  assert.match(source, /Sources/);
  assert.match(source, /Chunks/);
  assert.match(source, /Chat sessions/);
  assert.match(source, /Prompt data/);
  assert.match(source, /Citations/);
  assert.match(source, /Retrieval runs/);
  assert.match(source, /Required setup/);
  assert.match(source, /requiredModelsForSettings/);
  assert.match(source, /settingsSummaryRows/);
  assert.match(source, /Manifest summary/);
  assert.match(source, /buildExportManifestSummary/);
  assert.match(source, /chat_citations/);
  assert.match(source, /retrieval_runs/);
  assert.match(styles, /\.export-layout/);
  assert.match(styles, /\.export-grid/);
  assert.match(styles, /\.export-metrics/);
  assert.match(styles, /\.export-toggle/);
});
