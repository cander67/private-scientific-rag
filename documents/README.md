# Documents Workspace

This directory is for local/manual document corpora, not CI fixtures.

Tracked files in this tree should be limited to documentation, manifests, checks, notes, and empty
folder markers. Actual PDFs, OCR outputs, source bundles, downloaded corpora, and personal helper
scripts stay local and are ignored by Git.

Use `scripts/prepare_golden_corpus.sh` on macOS/Linux or Git Bash to recreate the golden-corpus
folder layout and review the required manual/downloaded files. On Windows PowerShell, create the
same folder layout with:

```powershell
$folders = "checks", "markdown", "notes", "ocr", "patents_uploaded", "pdf", "source_bundles", "text"
$folders | ForEach-Object { New-Item -ItemType Directory -Force -Path "documents/golden_corpus/$_" | Out-Null }
New-Item -ItemType File -Force -Path "documents/golden_corpus/source_bundles/.gitkeep", "documents/golden_corpus/text/.gitkeep" | Out-Null
```

A personal copy named `documents/recreate_golden_corpus.local.sh` is provided for Bash-based local
machines and is intentionally ignored. Windows users can keep equivalent private PowerShell notes
outside Git or in another ignored local helper file.

Default tests use fixtures from `tests/fixtures/`, not from this directory.
