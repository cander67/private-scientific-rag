# Documents Workspace

This directory is for local/manual document corpora, not CI fixtures.

Tracked files in this tree should be limited to documentation, manifests, checks, notes, and empty
folder markers. Actual PDFs, OCR outputs, source bundles, downloaded corpora, and personal helper
scripts stay local and are ignored by Git.

Use `scripts/prepare_golden_corpus.sh` to recreate the golden-corpus folder layout and review the
required manual/downloaded files. A personal copy named `documents/recreate_golden_corpus.local.sh`
is provided for local machines and is intentionally ignored.

Default tests use fixtures from `tests/fixtures/`, not from this directory.
