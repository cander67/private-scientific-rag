# PRD 12: Bulk Patent Data Integration

## Problem Statement

Researchers will eventually need to ingest patent data directly from raw patent-data sources rather than only uploading patent PDFs one at a time. Patent data arrives in multiple formats, changes by jurisdiction and era, and may include XML, SGML, APS text, TIFF/PDF images, ZIP archives, assignment records, classifications, legal status, bibliographic records, claims, drawings, and family metadata. The RAG system needs a careful integration plan before it handles those feeds.

## Solution

Add a patent-data ingestion layer after PRD3 that can retrieve or accept bulk patent sources, normalize records into the private RAG document model, preserve archive provenance, and expose patent-specific metadata for retrieval and citation. The recommended integration target is the `patent_client` Python library as the primary application dependency, with `patent-client-agents` used as an optional research and MCP exploration aid, and USPTO data portals used as authoritative US source systems.

Research notes:

- `patent_client` is a Python package for public intellectual-property data with ORM-style models, async support, caching, Pydantic v2 models, pandas conversion, and coverage for USPTO, EPO OPS/INPADOC, USPTO bulk data, Global Dossier, assignments, PTAB, and Patent Public Search. PyPI lists the latest release checked here as `5.0.19`, released April 8, 2025. Sources: https://pypi.org/project/patent_client/ and https://patent-client.readthedocs.io/en/latest/motivation.html.
- `patent_client` explicitly supports USPTO Bulk Data Storage System discovery/download flows through products and files, including patent grant/application XML, bibliographic data, full text, multi-page PDF images, and related datasets. Source: https://patent-client.readthedocs.io/en/latest/user_guide/bulk_data.html.
- `patent-client-agents` exposes MCP tools for patent/IP data and broad jurisdiction exploration, including USPTO, EPO, JPO, Google Patents, CPC, WIPO Lex, and many national IP offices. It is useful for assisted research and prototyping, but less appropriate as the core ingestion dependency because the app needs deterministic local ingestion jobs and typed pipeline boundaries. Sources: https://docs.patentclient.com/ and https://github.com/parkerhancock/patent-client-agents.
- USPTO Data/Open Data Portal is authoritative for US patent source data, but it is US-specific. It should be integrated through a dedicated USPTO adapter or via `patent_client` rather than treated as a general multi-jurisdiction solution. Source: https://data.uspto.gov/home.

## User Stories

1. As a researcher, I can import a small subset of patent records from a bulk source, so that I can build a patent-aware RAG repository without manually downloading every PDF.
2. As a researcher, I can ingest US patent grant and application XML, so that full text, claims, abstracts, classifications, and bibliographic metadata are searchable.
3. As a researcher, I can attach PDF or image assets to a parsed patent record, so that drawings and page-image citations remain inspectable.
4. As a researcher, I can preserve source archive metadata, so that every patent record can be traced back to its downloaded archive, file, URL, date, and parser version.
5. As a researcher, I can filter by publication number, application number, jurisdiction, kind code, assignee/applicant, inventor, publication date, grant date, CPC/IPC, patent family, claims, examples, and legal-status fields where available.
6. As a researcher, I can limit import size before a job starts, so that large patent archives do not overwhelm a local machine.
7. As a researcher, I can inspect skipped, failed, malformed, or schema-variant records, so that bulk ingest problems are visible and recoverable.
8. As a researcher, I can keep patent-data API credentials local, so that the private RAG remains local-first.

## Scope

- Patent ingestion adapter interface for source discovery, download/import, parsing, normalization, and provenance.
- Initial `patent_client` integration for supported USPTO bulk data and EPO/INPADOC-style records where practical.
- File-based import path for already downloaded ZIP/XML/SGML/APS/TIFF/PDF patent data.
- Patent record model that maps bibliographic fields, claims, description sections, examples, classifications, applicants/assignees, inventors, priority/family metadata, and source assets into the existing document/chunk model.
- Local job controls for date range, jurisdiction, product/feed type, record count limit, storage limit, dry run, and resume.
- Parser registry for XML/SGML/APS variants and future jurisdiction-specific adapters.
- Inspection UI for patent import jobs and parsed patent records.
- Golden corpus extension with tiny, bounded patent-data samples after the PRD3 corpus is stable.

## Non-Goals

- This PRD does not replace PRD3 user-uploaded patent PDF ingestion.
- This PRD does not attempt full global patent-office parity in the first implementation.
- This PRD does not guarantee legal-status accuracy without source-specific validation.
- This PRD does not include paid commercial patent databases.
- This PRD does not require hosted processing or cloud storage.
- This PRD does not import full weekly USPTO image/PDF archives by default.

## Implementation Decisions

- Use `patent_client` as the first application-level library candidate because it is Python-native, typed with Pydantic v2 models, supports async access, includes caching, and covers both USPTO bulk data and non-US sources better than a USPTO-only portal integration.
- Keep `patent-client-agents` out of the core ingestion path for now. Use it for research, schema discovery, and possible operator-assist tooling if MCP integration becomes useful.
- Treat USPTO Data/Open Data Portal and Bulk Data Storage System as authoritative US sources, not a general multi-jurisdiction abstraction.
- Store raw source archives separately from normalized patent records and derived chunks.
- Require import limits and dry-run summaries before large archive processing.
- Normalize patent citations around publication/application identifiers plus source archive/file provenance, not only PDF page numbers.
- Keep jurisdiction-specific parsing behind adapters so future WIPO, JPO, KIPO, CNIPA, EPO, and national-office formats can be added without changing the retrieval layer.

## Testing Decisions

- Unit test parser normalization from representative patent XML/SGML/APS samples into the intermediate patent record model.
- Unit test source provenance fields for archive name, URL, checksum, source file path, record identifier, parser version, and import job ID.
- Integration test bounded import of 2-5 patent records from a local fixture archive.
- Integration test dry-run behavior, import limits, resume behavior, and malformed-record reporting.
- Retrieval tests should verify claims, abstracts, examples, classifications, assignees/applicants, and family metadata when present.
- Network/API tests must be opt-in and marked live, with credentials read only from local environment variables.

## Out of Scope

PRD3 remains focused on local user-uploaded files, including user-uploaded patent PDFs. PRD12 starts only after PRD3 ingestion, inspection, and provenance models are stable enough to receive normalized patent records from bulk or raw-data sources.

## Further Notes

Start with a local fixture archive and a tiny bounded USPTO grant/application XML sample. Add broader jurisdiction adapters only after the source model, provenance model, and patent-specific retrieval filters are proven with the first adapter.
