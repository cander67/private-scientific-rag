# Test Fixtures

Default CI fixtures should be small, redistributable, and deterministic.

PRD3 parser smoke tests intentionally avoid depending on anything in `documents/golden_corpus/`.
They use the committed lightweight text, annotation, and markdown fixtures in
`tests/fixtures/ingestion/`, then generate tiny PDFs in the test process for these behaviors:

- an image-backed PDF with an existing text layer parses without `needs_ocr`;
- an image-only PDF with no text layer is marked `needs_ocr` and produces no chunks.

Add binary files here only when a behavior cannot be generated reliably in test code.
