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
  assert.match(source, /function ocrPendingPages/);
  assert.match(source, /OCR pending/);
  assert.match(source, /recoveredPages\.has\(route\.page\)/);
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
  assert.match(source, /OCR recovered/);
  assert.match(source, /page-ocr-recovered/);
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

test("Document Manager supports multi-select batch toolbar controls", () => {
  assert.match(source, /type DocumentBatchResponse =/);
  assert.match(source, /selectedBatchDocumentIds/);
  assert.match(source, /function toggleBatchDocument/);
  assert.match(source, /function selectVisibleDocuments/);
  assert.match(source, /function clearVisibleDocuments/);
  assert.match(source, /function clearBatchSelection/);
  assert.match(source, /className="document-selection-controls row row-between"/);
  assert.match(source, /Select visible/);
  assert.match(source, /Clear selection/);
  assert.match(source, /selectedBatchDocumentIds\.length > 0 && \(/);
  assert.match(source, /className="document-batch-toolbar"/);
  assert.match(source, /Reprocess selected/);
  assert.match(source, /Run OCR selected/);
  assert.match(source, /Delete selected/);
});

test("Document Manager calls PRD28 batch endpoints with guarded confirmations", () => {
  assert.match(source, /documents\/batch\/\$\{action\}/);
  assert.match(source, /function batchReprocessSelected/);
  assert.match(source, /function batchRunOcrSelected/);
  assert.match(source, /function batchDeleteSelected/);
  assert.match(source, /function batchReprocessAllDocuments/);
  assert.match(source, /Delete \$\{count\} selected document/);
  assert.match(source, /Reprocess all \$\{documents\.length\} document/);
  assert.match(source, /all_repository_documents: options\.allRepositoryDocuments === true/);
});

test("Document Manager renders batch eligibility and partial outcomes", () => {
  assert.match(source, /ocrEligibleCount\(selectedBatchDocuments\)/);
  assert.match(source, /reprocessUnavailableCount\(selectedBatchDocuments\)/);
  assert.match(source, /function DocumentBatchResultPanel/);
  assert.match(source, /documentBatchStatusCounts/);
  assert.match(source, /documentBatchCountsLabel/);
  assert.match(source, /BatchStatusBadge/);
  assert.match(source, /missing_source/);
  assert.match(source, /missing_dependency/);
  assert.match(source, /ineligible/);
  assert.match(source, /No documents were selected for this batch/);
});

test("Document Manager refreshes rows, Source Viewer, and readiness after batches", () => {
  assert.match(source, /function refreshDocumentManagerAfterBatch/);
  assert.match(source, /await loadDocuments\(repositoryId\)/);
  assert.match(source, /await loadChatReadiness\(repositoryId\)/);
  assert.match(source, /await loadDashboardSummary\(repositoryId\)/);
  assert.match(source, /inspectDocument\(repositoryId, inspectionTargetId\)/);
  assert.match(source, /refreshedDocuments\.some\(\(document\) => document\.id === inspectionTargetId\)/);
  assert.match(source, /await refreshDocumentManagerAfterBatch\(repository\.id, payload, deletedIds\)/);
});

test("Document Manager surfaces stale retrieval guidance after content-changing batches", () => {
  assert.match(source, /function documentBatchChangesRepositoryContent/);
  assert.match(source, /outcome\.status === "deleted"/);
  assert.match(source, /outcome\.action === "reprocess"/);
  assert.match(source, /outcome\.action === "ocr"/);
  assert.match(source, /setLastRebuild\(null\)/);
  assert.match(source, /setSearchResults\(\[\]\)/);
  assert.match(source, /Document content changed; rebuild full-text\/vector indexes/);
  assert.match(source, /Document content changed; check retrieval readiness/);
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
