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
