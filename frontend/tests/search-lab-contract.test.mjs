import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");

test("Search Lab calls PRD4 full-text rebuild and search endpoints", () => {
  assert.match(source, /full-text\/rebuild/);
  assert.match(source, /full-text\/search/);
  assert.match(source, /type FullTextSearchResult =/);
  assert.match(source, /type FullTextRebuildResponse =/);
});

test("Search Lab renders rank, BM25, snippets, filters, and provenance", () => {
  assert.match(source, /BM25/);
  assert.match(source, /dangerouslySetInnerHTML/);
  assert.match(source, /matched_fields/);
  assert.match(source, /has_table/);
  assert.match(source, /patent_section/);
  assert.match(source, /Citation:/);
  assert.match(source, /searchProvenanceLabel/);
});

test("Search Lab can route a result into Source Viewer", () => {
  assert.match(source, /function openSearchResult/);
  assert.match(source, /setSelectedDocumentId\(result\.document_id\)/);
  assert.match(source, /setSelectedChunkId\(result\.chunk_id\)/);
  assert.match(source, /navigateTo\("source"\)/);
  assert.match(source, /#search-lab/);
  assert.match(source, /#source-viewer/);
});

test("PRD5 and PRD6 controls remain disabled in PRD4", () => {
  assert.match(source, /<button type="button" disabled>\s*Vector\s*<\/button>/);
  assert.match(source, /<button type="button" disabled>\s*Hybrid\s*<\/button>/);
  assert.match(source, /planned for PRD6/);
});
