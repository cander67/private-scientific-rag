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
  assert.match(source, /Summary API coming next/);
  assert.match(styles, /\.dashboard-layout/);
  assert.match(styles, /\.dashboard-grid/);
  assert.match(styles, /\.dashboard-metric/);
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
