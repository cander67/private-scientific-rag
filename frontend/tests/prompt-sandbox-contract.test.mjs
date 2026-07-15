import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("Prompt Sandbox is a first-class routed view", () => {
  assert.match(source, /type View = "documents" \| "source" \| "search" \| "sandbox" \| "chat" \| "settings" \| "export" \| "recreate"/);
  assert.match(source, /#prompt-sandbox/);
  assert.match(source, /navigateTo\("sandbox"\)/);
  assert.match(source, /activeView === "sandbox"/);
  assert.match(source, /Prompt Sandbox/);
});

test("Prompt Sandbox creates and runs persisted comparisons", () => {
  assert.match(source, /type SandboxPromptVersion =/);
  assert.match(source, /type SandboxComparison =/);
  assert.match(source, /prompt-sandbox\/prompts/);
  assert.match(source, /prompt-sandbox\/comparisons/);
  assert.match(source, /execute_immediately: false/);
  assert.match(source, /prompt-sandbox\/comparisons\/\$\{comparisonId\}\/runs/);
  assert.match(source, /saveSandboxPrompt/);
  assert.match(source, /deleteSandboxPrompt/);
  assert.match(source, /runSandboxComparison/);
  assert.match(source, /runSandboxComparisonRun/);
  assert.match(source, /sandboxComparisonRunConfigs/);
  assert.match(source, /Full-text/);
  assert.match(source, /Vector/);
  assert.match(source, /Hybrid/);
  assert.match(source, /Reranked hybrid/);
});

test("Prompt Sandbox renders side-by-side run cards with context links", () => {
  assert.match(source, /function PromptSandbox/);
  assert.match(source, /function SandboxRunCard/);
  assert.match(source, /type SandboxProgressRun/);
  assert.match(source, /progressRunsFromConfigs/);
  assert.match(source, /pending/);
  assert.match(source, /running/);
  assert.match(source, /completed/);
  assert.match(source, /failed/);
  assert.match(source, /sandbox-run-grid/);
  assert.match(source, /sandbox-run-card/);
  assert.match(source, /context_entries/);
  assert.match(source, /score_breakdown/);
  assert.match(source, /sandboxPromptSnapshotName/);
  assert.match(source, /<dt>prompt<\/dt>/);
  assert.match(source, /<dt>context<\/dt>/);
  assert.match(source, /onOpenContext/);
  assert.match(source, /openSandboxContext/);
  assert.match(source, /View source/);
  assert.match(styles, /\.sandbox-run-grid[\s\S]*grid-template-columns: repeat\(4/);
  assert.match(styles, /\.sandbox-run-card/);
});

test("Prompt Sandbox reflects user-testing remediation states", () => {
  assert.match(source, /Delete version/);
  assert.match(source, /will not change normal chat behavior/);
  assert.match(source, /method: "DELETE"/);
  assert.match(source, /Running comparison\.\.\./);
  assert.match(source, /aria-busy=\{busy\}/);
  assert.match(source, /formatLatencySeconds/);
  assert.match(source, /toFixed\(1\)} s/);
  assert.match(styles, /\.btn-running:disabled[\s\S]*opacity: 1/);
  assert.match(styles, /\.sandbox-run-card-running/);
  assert.match(styles, /\.badge-running/);
});
