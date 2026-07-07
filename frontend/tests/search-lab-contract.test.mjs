import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");

test("Search Lab calls PRD4 full-text and PRD5 vector search endpoints", () => {
  assert.match(source, /endpoint = searchMode === "vector" \? "vector" : "full-text"/);
  assert.match(source, /\$\{endpoint\}\/rebuild/);
  assert.match(source, /\$\{endpoint\}\/search/);
  assert.match(source, /type FullTextSearchResult =/);
  assert.match(source, /type FullTextRebuildResponse =/);
  assert.match(source, /type VectorSearchResult =/);
  assert.match(source, /type VectorRebuildResponse =/);
});

test("Search Lab renders full-text and vector result details", () => {
  assert.match(source, /BM25/);
  assert.match(source, /Dense/);
  assert.match(source, /embedding_model/);
  assert.match(source, /embedding_run_id/);
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

test("PRD5 vector mode is enabled and PRD6 hybrid remains disabled", () => {
  assert.match(source, /onModeChange\("vector"\)/);
  assert.match(source, /<button type="button" disabled>\s*Hybrid\s*<\/button>/);
  assert.match(source, /planned for PRD6/);
});
