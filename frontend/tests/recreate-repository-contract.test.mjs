import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("Recreate Repository is a first-class routed view", () => {
  assert.match(source, /type View = "documents" \| "source" \| "search" \| "sandbox" \| "chat" \| "export" \| "recreate"/);
  assert.match(source, /#recreate-repository/);
  assert.match(source, /navigateTo\("recreate"\)/);
  assert.match(source, /activeView === "recreate"/);
  assert.match(source, /function RecreateRepository/);
  assert.match(source, /Recreate Repository/);
});

test("Recreate Repository validates uploaded bundles before enabling recreate", () => {
  assert.match(source, /const \[recreateFile, setRecreateFile\] = useState<File \| null>\(null\)/);
  assert.match(source, /repositories\/recreate\/bundle\/validate/);
  assert.match(source, /function validateRecreateBundle/);
  assert.match(source, /Validate bundle/);
  assert.match(source, /validation\?\.can_recreate/);
  assert.match(source, /disabled=\{!canRecreate\}/);
  assert.match(source, /Bundle has blocking issues/);
});

test("Recreate Repository supports source mappings and model hints", () => {
  assert.match(source, /type RecreateSourceMapping =/);
  assert.match(source, /source_mappings_json/);
  assert.match(source, /available_models_json/);
  assert.match(source, /mergeSourceMappings/);
  assert.match(source, /missing_external_source_mapping/);
  assert.match(source, /external_source_hash_mismatch/);
  assert.match(source, /Source hash/);
  assert.match(source, /Local path/);
  assert.match(source, /Add mapping/);
  assert.match(source, /External files/);
});

test("Recreate Repository displays validation groups and final report", () => {
  assert.match(source, /Blocking errors/);
  assert.match(source, /Warnings/);
  assert.match(source, /Information/);
  assert.match(source, /IssueGroup/);
  assert.match(source, /Missing model/);
  assert.match(source, /Parser\/settings fingerprint/);
  assert.match(source, /Count mismatch/);
  assert.match(source, /Final report/);
  assert.match(source, /full-text index/);
  assert.match(source, /vector index/);
  assert.match(source, /recreateProgressSteps/);
  assert.match(styles, /\.recreate-layout/);
  assert.match(styles, /\.recreate-grid/);
  assert.match(styles, /\.recreate-issue-grid/);
  assert.match(styles, /\.recreate-step-running/);
});

test("Recreate Repository calls execution endpoint with target options", () => {
  assert.match(source, /function runRecreateBundle/);
  assert.match(source, /repositories\/recreate\/bundle`/);
  assert.match(source, /repository_name/);
  assert.match(source, /target_repository_id/);
  assert.match(source, /Existing empty repository ID/);
  assert.match(source, /Recreating repository/);
  assert.match(source, /Recreate complete/);
  assert.match(source, /Recreate failed/);
});
