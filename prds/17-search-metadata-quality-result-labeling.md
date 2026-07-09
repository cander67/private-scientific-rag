# PRD 17: Search Metadata Quality and Result Labeling

**Status:** Backlog.

## Problem Statement

Search Lab result cards currently display metadata pills such as `patent_pdf`, `claims`, `abstract`, `table`, and `figure`. These labels are useful when they are accurate, but they can be misleading when broad document-level hints are shown on every matching chunk or when parser heuristics infer a document kind too aggressively.

From a researcher's perspective, the pills should answer a simple question: "What is true about this specific result?" Today, some pills answer a broader question: "What was detected somewhere in this document or document version?" That makes manual search evaluation harder, especially for patent PDFs where `claims`, `abstract`, and similar labels can appear even when the matched chunk is not from that section.

## Solution

Improve ingestion, parsing, indexing, retrieval metadata, and Search Lab display so result labels distinguish between chunk-level facts, document-level facts, parser hints, and active search filters.

The user-facing goal is not to hide metadata. It is to make each label precise enough that a researcher can tell whether a result is a claim, an abstract, a patent PDF, a table-backed chunk, a figure-backed chunk, or merely part of a document where those features were detected elsewhere.

This PRD should introduce a clearer metadata model with explicit scope, improve patent-section assignment during parsing/chunking, and update Search Lab result cards so pills no longer imply more precision than the backend can support.

## User Stories

1. As a researcher, I want result labels to describe the matched chunk when possible, so that I can quickly judge whether a search result is relevant.
2. As a researcher, I want document-level labels to be visually or textually distinct from chunk-level labels, so that I do not confuse broad document hints with specific result facts.
3. As a researcher, I want patent section labels like `claims`, `abstract`, and `description` to appear only when they apply to the matched chunk or clearly be marked as document-level hints, so that I can trust search results during patent review.
4. As a researcher, I want `patent_pdf` to reflect a confident document classification, so that ordinary PDFs with incidental patent-like words are not mislabeled.
5. As a researcher, I want table and figure labels to reflect actual chunk or nearby-page evidence when available, so that I can find results backed by structured content.
6. As a researcher, I want Search Lab to show active filters separately from result metadata, so that I can distinguish what I asked for from what the result contains.
7. As a researcher, I want Source Viewer to expose the same metadata scope used by Search Lab, so that I can audit why a result received its labels.
8. As a researcher, I want reprocessing to refresh metadata after parser improvements, so that existing documents can benefit from better labels.
9. As a maintainer, I want metadata assignment to be centralized and testable, so that full-text, vector, hybrid, and chat workflows stay consistent.
10. As a maintainer, I want parser confidence and provenance recorded for inferred metadata, so that uncertain labels can be handled conservatively.
11. As a maintainer, I want existing repositories to migrate safely, so that current documents do not break when the metadata model becomes more precise.
12. As a maintainer, I want deterministic fixtures for section labeling, so that regressions in claims/abstract/table/figure metadata are caught early.
13. As a maintainer, I want live or golden-corpus checks to cover realistic patent PDFs, so that the heuristics are validated beyond tiny synthetic text.

## Implementation Decisions

- Introduce explicit metadata scope categories: chunk-level metadata, document-version metadata, parser hints, and active search request filters.
- Keep document-level metadata available, but do not render it as if it were chunk-level metadata.
- Update ingestion so parsed segments can carry section labels and parser-derived metadata before chunking.
- Improve patent-section detection from whole-document hinting toward section-boundary assignment. Patent section labels should attach to segments or chunks when the parser can identify a local section boundary.
- Make `document_kind` assignment more conservative. A PDF should be marked as `patent_pdf` only when there is enough patent-specific evidence, not merely because one patent-like section word appears.
- Preserve confidence or reason metadata for inferred labels where practical. Examples include "detected heading", "document-level hint", or "filename/source hint".
- Update full-text and vector indexing payloads so filters and result metadata use the same scoped metadata contract.
- Update unified retrieval so full-text, vector, and hybrid results expose consistent scoped metadata.
- Update Search Lab result cards to separate result facts from active filters and broad document hints.
- Keep backward compatibility for older indexed metadata during migration or reindexing. If older data cannot provide chunk-level scope, display it as a document hint rather than a chunk fact.
- Add a reprocess/rebuild path expectation: after metadata parsing changes, users should be able to reprocess documents and rebuild indexes to refresh result labels.

## Testing Decisions

- Tests should assert external behavior: which labels appear on uploaded/searchable documents and how they are scoped. They should avoid depending on private parser helper internals.
- Unit tests should cover source-type detection, patent document-kind confidence, patent section boundary detection, and chunk metadata assignment.
- Integration tests should upload representative PDFs/text fixtures, rebuild full-text and vector indexes, and confirm Search Lab/retrieval responses expose scoped metadata consistently.
- Retrieval tests should confirm full-text, vector, and hybrid modes return the same metadata semantics for the same chunk.
- UI contract tests should confirm Search Lab distinguishes active filters from result metadata and does not render document-level patent hints as chunk facts.
- Golden-corpus or opt-in live checks should include at least one realistic patent PDF with abstract, claims, description, examples, and drawings, plus one non-patent scientific PDF containing patent-like incidental language.
- Regression tests should cover the current failure mode: a document with claims elsewhere should not show `claims` on unrelated chunks unless that label is explicitly marked as a document-level hint.

## Out of Scope

- Bulk patent data ingestion from USPTO, EPO, WIPO, or other feeds.
- Full patent family normalization, assignee normalization, jurisdiction mapping, or legal-status metadata.
- Perfect patent parsing across every PDF layout.
- Full OCR implementation for scanned patents.
- Chemistry entity extraction beyond preserving existing metadata behavior.
- New reranking strategies based on improved metadata, unless needed to keep current metadata boost behavior correct.
- Replacing the existing Search Lab result-card design beyond the changes needed to clarify metadata scope.

## Further Notes

- This PRD is related to PRD3, PRD10, and PRD11, but it is narrower. PRD3 introduced ingestion and first-pass patent hints. PRD10 focuses on structured scientific and multimodal parsing. PRD11 focuses on chemistry and deeper patent extensions. This PRD focuses specifically on making labels trustworthy in retrieval and Search Lab.
- The current implementation copies version-level `patent_section_hints` into indexed chunk metadata, which causes broad hints like `claims` and `abstract` to appear on result cards even when the matched chunk may not be from that section.
- A useful implementation pattern would be a small metadata classification module that takes parsed document, segment, chunk, and version context and returns a scoped metadata object. That module can become the single place where confidence, scope, and display labels are decided.
- Metadata boosts from PRD6 should be reviewed after this work. Boosting should prefer chunk-level facts and use document-level hints more cautiously.
