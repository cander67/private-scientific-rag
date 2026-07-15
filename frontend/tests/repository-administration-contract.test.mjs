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

test("Repository Administration loads local inventory before destructive actions", () => {
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

  const adminComponent = source.match(/function RepositoryAdministration[\s\S]*?function RepositoryCleanupPreviewPanel/)?.[0] ?? "";
  assert.doesNotMatch(adminComponent, /method: "DELETE"|Execute cleanup/);
});

test("Repository Administration previews cleanup plans before confirmed deletion", () => {
  assert.match(source, /type RepositoryDeletePreview =/);
  assert.match(source, /type RepositoryDeleteResult =/);
  assert.match(source, /previewRepositoryCleanup/);
  assert.match(source, /deleteRepositoryFromPreview/);
  assert.match(source, /repositories\/\$\{repositoryId\}\/admin\/delete-preview/);
  assert.match(source, /repositories\/\$\{deletePreview\.repository\.id\}\/admin\/delete/);
  assert.match(source, /Preview cleanup/);
  assert.match(source, /RepositoryCleanupPreviewPanel/);
  assert.match(source, /RepositoryCleanupResultPanel/);
  assert.match(source, /database_counts/);
  assert.match(source, /warnings/);
  assert.match(source, /adminCleanupActionLabel/);
  assert.match(source, /confirmationValue === preview\.repository\.name/);
  assert.match(source, /Type repository name to confirm/);
  assert.match(source, /Delete repository/);
  assert.match(source, /Cleanup result/);
  assert.match(source, /removed: RepositoryCleanupResultItem\[\]/);
  assert.match(source, /preserved: RepositoryCleanupResultItem\[\]/);
  assert.match(source, /failed: RepositoryCleanupResultItem\[\]/);
  assert.match(source, /No records, files, indexes, or model\s+[\s\S]*?caches are changed by this preview/);
  assert.match(source, /Retry available after the local service is reachable/);
});

test("Repository Administration retries failed vector cleanup without another delete", () => {
  assert.match(source, /type RepositoryVectorCleanupRetryResult =/);
  assert.match(source, /retryVectorCleanup/);
  assert.match(source, /repositories\/admin\/vector-cleanup\/retry/);
  assert.match(source, /collection_names: collectionNames/);
  assert.match(source, /VectorCleanupRetryPanel/);
  assert.match(source, /Retry Qdrant cleanup/);
  assert.match(source, /Retry vector cleanup/);
  assert.match(source, /does not require deleting the repository again/);
  assert.match(source, /vectorCleanupRetryCollectionNames/);
  assert.match(source, /Retry removed/);
  assert.match(source, /Retry failed/);
});

test("Repository Administration supports guarded clear-all preview and recovery", () => {
  assert.match(source, /type RepositoryClearAllPreview =/);
  assert.match(source, /type RepositoryClearAllResult =/);
  assert.match(source, /previewClearAllRepositories/);
  assert.match(source, /clearAllRepositories/);
  assert.match(source, /repositories\/admin\/clear-all\/preview/);
  assert.match(source, /repositories\/admin\/clear-all/);
  assert.match(source, /Preview clear all/);
  assert.match(source, /RepositoryClearAllPreviewPanel/);
  assert.match(source, /RepositoryClearAllResultPanel/);
  assert.match(source, /confirmationValue === preview\.confirmation_value/);
  assert.match(source, /Type confirmation phrase/);
  assert.match(source, /Clear all local repositories/);
  assert.match(source, /default_repository: RepositorySettingsResponse/);
  assert.match(source, /Open Repository Dashboard/);
  assert.match(source, /Open Recreate Repository/);
});

test("Repository Administration has stable layout hooks", () => {
  assert.match(styles, /\.admin-layout/);
  assert.match(styles, /\.admin-overview/);
  assert.match(styles, /\.admin-totals/);
  assert.match(styles, /\.admin-index-pill/);
  assert.match(styles, /\.admin-hints/);
  assert.match(styles, /\.admin-preview-panel/);
  assert.match(styles, /\.admin-plan-retry_required/);
  assert.match(styles, /\.admin-confirm-delete/);
  assert.match(styles, /\.admin-result-grid/);
});
