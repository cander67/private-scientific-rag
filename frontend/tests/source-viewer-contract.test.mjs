import assert from "node:assert/strict";
import { readFile } from "node:fs/promises";
import test from "node:test";

const source = await readFile(new URL("../src/main.tsx", import.meta.url), "utf8");

test("Source Viewer consumes PRD3 page-image inspection data", () => {
  assert.match(source, /type PageImage =/);
  assert.match(source, /page_images: PageImage\[\]/);
  assert.match(source, /function PageImageStrip/);
  assert.match(source, /absoluteApiUrl\(image\.url\)/);
});

test("Source Viewer opens PDFs with page images even when chunks are absent", () => {
  assert.match(source, /No parsed chunks yet/);
  assert.match(source, /No parsed chunks/);
  assert.match(source, /Page thumbnails and parser warnings are available/);
  assert.doesNotMatch(source, /\{inspection && selectedChunk \? \(/);
});

test("Source Viewer keeps PRD3 document actions and provenance visible", () => {
  assert.match(source, /function provenanceLabel/);
  assert.match(source, /Reprocess/);
  assert.match(source, /Delete/);
  assert.match(source, /version\.warnings\.join/);
  assert.match(source, /Patent PDF hints/);
  assert.match(source, /Source structure hints/);
});

test("Document Manager and Source Viewer expose parser reprocess status", () => {
  assert.match(source, /type ReprocessStatus =/);
  assert.match(source, /metadata\.reprocess_status/);
  assert.match(source, /function getReprocessStatus/);
  assert.match(source, /function reprocessStatusLabel/);
  assert.match(source, /Stale: \$\{status\.changed_fields\.join/);
  assert.match(source, /<dt>Reprocess<\/dt>/);
  assert.match(source, /<dt>reprocess<\/dt>/);
});

test("Document Manager and Source Viewer render as separate live views", () => {
  assert.match(source, /activeView === "documents"/);
  assert.match(source, /activeView === "source"/);
  assert.match(source, /navigateTo\("source"\)/);
  assert.match(source, /activeView === "documents" && \(/);
  assert.match(source, /activeView === "source" && \(inspection \? \(/);
  assert.match(source, /activeView === "documents"[\s\S]*className="btn btn-primary upload-button"/);
});

test("Document Manager supports direct row delete and delete all actions", () => {
  assert.match(source, /function deleteDocument/);
  assert.match(source, /function deleteAllDocuments/);
  assert.match(source, /Delete all/);
  assert.match(source, /className="row table-actions"/);
  assert.match(source, /onClick=\{\(\) => void deleteDocument\(document\.id\)\}/);
  assert.match(source, /window\.confirm\(`Delete \$\{document\?\.display_name/);
  assert.match(source, /DELETE/);
});
