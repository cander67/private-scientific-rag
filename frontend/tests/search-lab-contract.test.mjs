import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");

test("Search Lab rebuilds underlying indexes and searches through unified retrieval", () => {
  assert.match(source, /full-text\/rebuild/);
  assert.match(source, /vector\/rebuild/);
  assert.match(source, /retrieval\/search/);
  assert.match(source, /\$\{endpoint\}\/rebuild/);
  assert.match(source, /type RetrievalSearchResult =/);
  assert.match(source, /type RetrievalSearchResponse =/);
  assert.match(source, /type FullTextRebuildResponse =/);
  assert.match(source, /type VectorRebuildResponse =/);
});

test("Search Lab renders retrieval score breakdown details", () => {
  assert.match(source, /BM25/);
  assert.match(source, /Dense/);
  assert.match(source, /RRF/);
  assert.match(source, /Rerank/);
  assert.match(source, /Boost/);
  assert.match(source, /Final/);
  assert.match(source, /source_ranks/);
  assert.match(source, /score_breakdown/);
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

test("PRD6 hybrid mode and reranking controls are enabled", () => {
  assert.match(source, /onModeChange\("vector"\)/);
  assert.match(source, /onModeChange\("hybrid"\)/);
  assert.match(source, /reranker-strategy/);
  assert.match(source, /cross_encoder_metadata_boost/);
  assert.match(source, /candidate-pool-size/);
  assert.match(source, /rrf-constant/);
  assert.match(source, /metadata-boost-level/);
  assert.match(source, /Diversity\/MMR - future/);
});
