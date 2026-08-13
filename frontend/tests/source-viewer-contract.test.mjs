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

test("Source Viewer displays PRD13 page OCR routing state", () => {
  assert.match(source, /type PageOcrRoute =/);
  assert.match(source, /metadata\.page_ocr_routes/);
  assert.match(source, /function getPageOcrRoutes/);
  assert.match(source, /function ocrPageLabel/);
  assert.match(source, /OCR pending/);
  assert.match(source, /Mixed · native text/);
  assert.match(source, /className=\{ocrPageClassName\(version, image\.page\)\}/);
});

test("Source Viewer supports PRD13 local OCR recovery", () => {
  assert.match(source, /type OcrPageResult =/);
  assert.match(source, /function runOcrSelected/);
  assert.match(source, /documents\/\$\{selectedDocumentId\}\/ocr/);
  assert.match(source, /Run OCR/);
  assert.match(source, /function OcrPageTextPanel/);
  assert.match(source, /metadata\.ocr_pages/);
  assert.match(source, /OCR text/);
  assert.match(source, /function isOcrChunk/);
});

test("Source Viewer renders parser names before parser versions", () => {
  assert.match(source, /function parserDisplayLabel/);
  assert.match(source, /function parserNameLabel/);
  assert.match(source, /function parserRouteLabel/);
  assert.match(source, /parserDisplayLabel\(inspection\.version\)/);
  assert.match(source, /<dt>parser version<\/dt>/);
  assert.match(source, /<dt>Parser version<\/dt>/);
  assert.match(source, /Built-in parser/);
});

test("Source Viewer displays PRD30 chunk tokenizer metadata", () => {
  assert.match(source, /tokenWindowLabel/);
  assert.match(source, /chunkTokenizerLabel/);
  assert.match(source, /chunkTokenizerPrecisionLabel/);
  assert.match(source, /tokenizerMetadata/);
  assert.match(source, /implementation_library/);
  assert.match(source, /selection_mode/);
  assert.match(source, /offset_mapping/);
  assert.match(source, /<dt>tokens<\/dt>/);
  assert.match(source, /<dt>chunk tokenizer<\/dt>/);
  assert.match(source, /<dt>tokenizer precision<\/dt>/);
});

test("Document Manager and Source Viewer render as separate live views", () => {
  assert.match(source, /activeView === "documents"/);
  assert.match(source, /activeView === "source"/);
  assert.match(source, /navigateTo\("source"\)/);
  assert.match(source, /activeView === "documents" && \(/);
  assert.match(source, /activeView === "source" && \(inspection \? \(/);
  assert.match(source, /activeView === "documents"[\s\S]*className="btn btn-primary upload-button"/);
});

test("Document Manager previews selected rows without opening Source Viewer", () => {
  const selectionEffects = source.slice(
    source.indexOf("const [pendingSourceTarget"),
    source.indexOf("const selectedDocument = useMemo"),
  );
  assert.match(source, /className=\{[\s\S]*?"selectable-row selected-row"[\s\S]*?: "selectable-row"/);
  assert.match(source, /onClick=\{\(\) => setSelectedDocumentId\(document\.id\)\}/);
  assert.match(source, /onKeyDown=\{\(event\) => \{[\s\S]*setSelectedDocumentId\(document\.id\)/);
  assert.match(source, /const version = selectedDocument\?\.current_version \?\? null/);
  assert.match(source, /<dt>Reprocess<\/dt>[\s\S]*reprocessStatusLabel\(version\)/);
  assert.doesNotMatch(selectionEffects, /inspectDocument\(repository\.id, selectedDocumentId\)/);
});

test("Document Manager keeps Source Viewer inspection explicit", () => {
  assert.match(source, /function openSelectedDocumentInSource/);
  assert.match(source, /inspectDocument\(repository\.id, selectedDocumentId\)/);
  assert.match(source, /onOpenSource=\{openSelectedDocumentInSource\}/);
  assert.match(source, /Open in Source Viewer/);
  assert.match(source, /disabled=\{busy \|\| reprocessStatus\?\.reprocess_available === false\}/);
  assert.match(source, /disabled=\{busy \|\| version\.source_type !== "pdf" \|\| !version\.ocr_required\}/);
});

test("Document Manager supports direct row delete and delete all actions", () => {
  assert.match(source, /function deleteDocument/);
  assert.match(source, /function deleteAllDocuments/);
  assert.match(source, /Delete all/);
  assert.match(source, /className="row table-actions"/);
  assert.match(source, /event\.stopPropagation\(\);[\s\S]*void deleteDocument\(document\.id\)/);
  assert.match(source, /window\.confirm\(`Delete \$\{document\?\.display_name/);
  assert.match(source, /DELETE/);
});
