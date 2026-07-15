import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("Repository Administration is routed and visible in the management shell", () => {
  assert.match(source, /type View =[\s\S]*?"admin"/);
  assert.match(source, /function RepositoryAdministration/);
  assert.match(source, /Repository Administration/);
  assert.match(source, /href="#repository-administration"[\s\S]*?navigateTo\("admin"\)/);
  assert.match(source, /case "admin":[\s\S]*?return "repository-administration"/);
  assert.match(source, /hash === "#repository-administration" \|\| hash === "#admin"/);
  assert.match(source, /activeView === "admin"/);
});

test("Repository Administration loads local inventory without destructive actions", () => {
  assert.match(source, /type RepositoryAdminInventory =/);
  assert.match(source, /repositories\/admin\/inventory/);
  assert.match(source, /Local repository inventory/);
  assert.match(source, /does not manage remote or cloud/);
  assert.match(source, /counts\.documents/);
  assert.match(source, /counts\.chat_sessions/);
  assert.match(source, /counts\.retrieval_runs/);
  assert.match(source, /counts\.sandbox_runs/);
  assert.match(source, /AdminIndexPill/);
  assert.match(source, /storage_hints/);
  assert.match(source, /external_sources/);
  assert.match(source, /model_caches/);
  assert.match(source, /adminStorageStatusLabel/);

  const adminComponent = source.match(/function RepositoryAdministration[\s\S]*?function AdminIndexPill/)?.[0] ?? "";
  assert.doesNotMatch(adminComponent, /delete|clear|reset/i);
});

test("Repository Administration has stable layout hooks", () => {
  assert.match(styles, /\.admin-layout/);
  assert.match(styles, /\.admin-overview/);
  assert.match(styles, /\.admin-totals/);
  assert.match(styles, /\.admin-index-pill/);
  assert.match(styles, /\.admin-hints/);
});
