import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");
const styles = await readFile(new URL("../src/styles.css", import.meta.url), "utf8");

test("Repository Dashboard is the home route and has stable aliases", () => {
  assert.match(source, /type View =[\s\S]*?"dashboard"/);
  assert.match(source, /function RepositoryDashboard/);
  assert.match(source, /Repository Dashboard/);
  assert.match(source, /case "dashboard":[\s\S]*?return "repository-dashboard"/);
  assert.match(source, /hash === "" \|\| hash === "#" \|\| hash === "#home" \|\| hash === "#repository-dashboard"/);
  assert.match(source, /activeView === "dashboard"/);
});

test("Home and Repository Dashboard sidebar entries are navigable", () => {
  assert.match(source, /href="#home"[\s\S]*?navigateTo\("dashboard"\)[\s\S]*?Home/);
  assert.match(source, /href="#repository-dashboard"[\s\S]*?navigateTo\("dashboard"\)[\s\S]*?Repository Dashboard/);
  assert.doesNotMatch(source, /<a>Home<\/a>/);
  assert.doesNotMatch(source, /<a>Repository Dashboard<\/a>/);
});

test("Dashboard shell shows active repository identity and basic metadata", () => {
  assert.match(source, /repository\?\.name \?\? "No active repository"/);
  assert.match(source, /repository\?\.id \?\? "unavailable"/);
  assert.match(source, /repository\?\.root_path \?\? "local default"/);
  assert.match(source, /repository\?\.created_at \? formatDate\(repository\.created_at\)/);
  assert.match(source, /repository\?\.updated_at \? formatDate\(repository\.updated_at\)/);
  assert.match(source, /repositories\/\${repositoryId}\/summary/);
  assert.match(styles, /\.dashboard-layout/);
  assert.match(styles, /\.dashboard-grid/);
  assert.match(styles, /\.dashboard-metric/);
});

test("Dashboard status surface renders summary counts, readiness, config, and warnings", () => {
  assert.match(source, /type DashboardSummary =/);
  assert.match(source, /counts\?\.documents/);
  assert.match(source, /counts\?\.retrieval_runs/);
  assert.match(source, /counts\?\.sandbox_runs/);
  assert.match(source, /counts\?\.exports/);
  assert.match(source, /counts\?\.recreate_events/);
  assert.match(source, /DashboardIndexCard/);
  assert.match(source, /dashboardIndexStatusLabel/);
  assert.match(source, /Runtime readiness/);
  assert.match(source, /dashboardReadinessItems/);
  assert.match(source, /dashboardConfigRows/);
  assert.match(source, /dashboardWarningLinks/);
  assert.match(source, /Open Settings \/ Models/);
  assert.match(source, /Open Search Lab/);
  assert.match(source, /Open Chat Workspace/);
  assert.match(source, /Open Document Manager/);
  assert.match(source, /Open Recreate Repository/);
  assert.match(styles, /\.dashboard-status-grid/);
  assert.match(styles, /\.dashboard-index-ready/);
  assert.match(styles, /\.dashboard-index-partial/);
  assert.match(styles, /\.dashboard-index-stale/);
  assert.match(styles, /\.dashboard-warning-list/);
});

test("Dashboard quick actions and recent activity route to workflow owners", () => {
  assert.match(source, /dashboardQuickActions/);
  assert.match(source, /Document Manager/);
  assert.match(source, /Search Lab/);
  assert.match(source, /Chat Workspace/);
  assert.match(source, /Prompt Sandbox/);
  assert.match(source, /Export Center/);
  assert.match(source, /Recreate Repository/);
  assert.match(source, /Settings \/ Models/);
  assert.match(source, /recent_activity: DashboardActivityItem\[\]/);
  assert.match(source, /Latest repository events/);
  assert.match(source, /dashboardActivityKindLabel/);
  assert.match(source, /onNavigate\(item\.route\)/);
  assert.match(source, /Upload documents, search, chat, run sandbox checks, export, or recreate/);
  const quickActionsHelper = source.match(/function dashboardQuickActions[\s\S]*?function dashboardActivityKindLabel/)?.[0] ?? "";
  assert.doesNotMatch(quickActionsHelper, /method: "POST"|fetch\(/);
  assert.match(styles, /\.dashboard-quick-actions/);
  assert.match(styles, /\.dashboard-activity-list/);
  assert.match(styles, /\.dashboard-activity/);
});

test("Dashboard supports repository switching and no-repository recovery", () => {
  assert.match(source, /repositories=\{repositories\}/);
  assert.match(source, /onSelectRepository=\{activateRepository\}/);
  assert.match(source, /onUseDefaultRepository=\{\(\) => void useDefaultRepository\(\)\}/);
  assert.match(source, /async function useDefaultRepository\(\)/);
  assert.match(source, /fetch\(`\$\{API_BASE\}\/repositories\/default`\)/);
  assert.match(source, /id="dashboard-repository"/);
  assert.match(source, /repositories\.length > 1/);
  assert.match(source, /onSelectRepository\(selectedRepository\)/);
  assert.match(source, /No local repository is active/);
  assert.match(source, /Use default repository/);
  assert.match(source, /Open Recreate Repository/);
  assert.match(source, /activateRepository\(recreatedRepository\)/);
  assert.match(styles, /\.dashboard-empty/);
  assert.match(styles, /\.dashboard-repository-picker/);

  const dashboardComponent = source.match(/function RepositoryDashboard[\s\S]*?function DashboardIndexCard/)?.[0] ?? "";
  assert.doesNotMatch(dashboardComponent, /Delete all|reset/i);
});

test("Existing workspace routes remain routed after dashboard aliasing", () => {
  assert.match(source, /#documents/);
  assert.match(source, /#source-viewer/);
  assert.match(source, /#search-lab/);
  assert.match(source, /#prompt-sandbox/);
  assert.match(source, /#chat-workspace/);
  assert.match(source, /#export-center/);
  assert.match(source, /#recreate-repository/);
  assert.match(source, /#settings-models/);
});
