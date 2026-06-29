# PRD 10: Structured Scientific and Multimodal Parsing

## Goal

Improve scientific document understanding by extracting layout-aware pages, sections, tables, figures, captions, and multimodal metadata.

## User Stories

- As a researcher, I can inspect table and figure citations.
- As a researcher, I can retrieve chunks backed by captions, tables, or nearby explanatory text.
- As a maintainer, I can fall back gracefully when structured parsing fails.

## Scope

- Structured PDF parser adapter upgrades.
- Table asset extraction where available.
- Figure/caption asset extraction where available.
- Asset-aware chunks.
- Source Viewer asset inspection.
- Search filters for table/figure-backed chunks.

## Non-Goals

- Perfect OCR for scanned PDFs.
- Chemical structure recognition from images.
- Full multimodal embedding pipeline.

## Acceptance Criteria

- Table/caption chunks include table provenance.
- Figure caption chunks include figure provenance.
- Source cards expose page/table/figure details.
- Parser fallback works when structured parsing fails.
- Multimodal metadata appears in search filters and citations.

## Test Plan

- Golden corpus includes table and figure-caption PDFs.
- Unit test asset metadata mapping.
- Integration test source viewer asset inspection.
- Integration test citations to table/figure-backed chunks.

## Documentation References

- Docling documentation: https://docling-project.github.io/docling/
- pypdf documentation: https://pypdf.readthedocs.io/
- Azure multimodal search overview: https://learn.microsoft.com/en-us/azure/search/multimodal-search-overview
- `tests/README.md` for golden corpus conventions.
