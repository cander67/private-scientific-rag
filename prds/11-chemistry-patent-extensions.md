# PRD 11: Chemistry and Patent Extensions

## Goal

Add text-first chemistry and patent metadata extraction to improve retrieval and filtering for chemical/materials science workflows.

## User Stories

- As a researcher, I can search and filter by chemical identifiers and formula-like strings.
- As a researcher, I can filter patent-like documents by claims, examples, assignees, CPC/IPC, or patent family metadata when available.
- As a maintainer, I can keep chemistry tooling optional so ingestion remains robust.

## Scope

- Text-first chemistry entity extractor.
- SMILES, InChI, CAS-like, and formula-like detection.
- Patent metadata extractor.
- Chemistry and patent filters.
- Optional RDKit validation adapter later.

## Non-Goals

- Image-to-structure recognition.
- Structure-aware molecular similarity search.
- Perfect chemical named-entity recognition.

## Acceptance Criteria

- SMILES/InChI/CAS/formula-like strings are detected in golden documents.
- Patent claims, examples, assignees, CPC, and IPC are indexed where present.
- Chemistry and patent filters work in full-text, vector, hybrid, and chat workflows.
- Invalid chemistry extraction does not break ingestion.
- Chemistry features remain optional.

## Test Plan

- Unit test regex/entity detection.
- Unit test invalid chemistry handling.
- Integration test metadata filters.
- Evaluation includes chemistry-heavy and patent-like queries.

## Documentation References

- RDKit documentation: https://www.rdkit.org/docs/
- OPSIN: https://opsin.ch.cam.ac.uk/
- SQLite FTS5 documentation: https://www.sqlite.org/fts5.html
- `tests/README.md` for chemistry-heavy golden corpus conventions.
