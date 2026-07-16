# Documentation

Project documentation should be public-safe and useful to future contributors.

Current documents:

- `../documents/README.md`: local/manual document workspace policy.
- `../documents/golden_corpus/golden_corpus_manifest.md`: current chemistry/materials golden corpus recipe and inventory.
- `../documents/golden_corpus/golden_corpus_manifest_v1.md`: frozen historical copy.
- `../scripts/prepare_golden_corpus.sh`: tracked Bash helper for recreating the local golden-corpus layout; Windows PowerShell setup commands are documented in `../documents/README.md`.
- `embedding_models.md`: supported embedding model registry, provider tradeoffs, setup commands, custom Ollama model guidance, and PRD15/PRD16 index boundary.
- `export_recreate.md`: PRD9 portable ZIP export/recreate transfer guide and cross-platform checklist.
- `public_repo_checklist.md`: first commit and public GitHub readiness.

As modules mature, add focused docs close to the code:

- `tests/README.md`
- `src/private_rag/README.md`
- `frontend/README.md`
- module READMEs for ingestion, retrieval, evaluation, and exports when those modules are created.
