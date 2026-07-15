# Export and Recreate Transfer Guide

PRD9 is complete and closed. It adds portable repository ZIP bundles and a recreate workflow for moving a local research repository between supported hosts: macOS, Windows-native Python/Ollama, and Linux/Ubuntu.

## Bundle Contents

Export Center creates a ZIP bundle from `POST /repositories/{repository_id}/exports/bundle`.

Each bundle contains:

- `manifest.json` with bundle schema version, generated timestamp, repository metadata, export options, required models, settings snapshot, payload paths, source metadata, exported counts, and warnings.
- `payloads/settings.json` with repository parser, chunking, full-text, vector, embedding, reranking, model, prompt, and export settings.
- `payloads/prompts.json` with repository prompt library data.
- `payloads/documents.json` and `payloads/chunks.json` with portable document and parsed chunk metadata.
- `payloads/retrieval.json` with retrieval runs and result metadata.
- `payloads/chat.json` with active chat sessions, messages, retrieval settings, and citation mappings.
- `sources/{sha256}/{filename}` for included source files when source inclusion is enabled.
- `payloads/sandbox.json` only when sandbox export is explicitly enabled.

The bundle deliberately excludes generated indexes and local model files:

- SQLite FTS5 tables are rebuilt during recreate.
- Qdrant collections and embedding vectors are rebuilt during recreate.
- SentenceTransformers, cross-encoder, and Ollama model files are never packaged.
- Runtime data such as `data/`, `.qdrant/`, `models/`, `exports/`, caches, logs, private corpora, and generated artifacts must remain untracked.

## Privacy And Public-Repo Cautions

Export bundles can contain private source files, full parsed text, prompts, chat messages, citations, and retrieval history. Treat ZIP exports as research data, not as public fixtures.

Do not commit export ZIPs unless they were built from redistributable fixtures and reviewed for sensitive text. Use `tests/fixtures/` for CI-safe examples and keep manual corpora under `documents/`.

## Export Workflow

1. Open Export Center.
2. Review repository counts, prompt data, citation data, and required models/settings.
3. Choose whether to include source files.
4. Leave sandbox runs/comparisons disabled unless that history is intentionally needed.
5. Export the ZIP and store it outside the repo unless it is a reviewed public fixture.

Source exclusion is useful when source files are large or already available on the target machine. Recreate then requires explicit external file mappings by deterministic SHA-256 hash and local path.

## Recreate Workflow

1. Open Recreate Repository.
2. Select the export ZIP.
3. Optionally list locally available models, separated by commas or new lines.
4. Validate the bundle before restore.
5. Resolve blocking errors. For source-excluded bundles, provide a local path for each required SHA-256 hash.
6. Recreate into a new repository by default, or provide an existing empty repository ID.
7. Review the final source and index report.

Recreate restores documents, chat history, retrieval history, and optionally sandbox data into the recreated repository. The app activates the recreated repository after a successful restore; the topbar repository selector can switch between local repositories later. Search Lab does not show prior query results by default, but searches run against the active repository. Prompt Sandbox shows restored sandbox runs only when sandbox data was included during export.

Recreate remaps restored chunk IDs so citations and retrieval results point at the recreated repository data.

## Warning And Error Meanings

- **Missing bundle payload**: A manifest-referenced JSON payload is absent or unreadable. The bundle cannot be recreated.
- **Source hash mismatch**: A packaged or mapped source file does not match the deterministic SHA-256 hash in the manifest. The bundle cannot be recreated from that file.
- **Missing external source mapping**: The bundle excluded source bytes and the target machine has not supplied a local file path for that source hash.
- **External source path changed**: A mapped file has the right hash but a different filename or location. Recreate can continue, and the change is reported for provenance.
- **Model availability not checked**: No available-model list was supplied. Validation does not inspect local Ollama or SentenceTransformers caches automatically.
- **Missing model**: A required embedding, reranking, or chat model was checked against a supplied available-model list and was not found in that list.
- **Parser/settings fingerprint**: Parser, chunking, or settings fingerprints may produce different chunks on another host or dependency version.
- **Count mismatch**: Payload counts differ from manifest counts. Treat this as a bundle consistency problem.
- **Index difference**: Recreate reports full-text and vector indexed chunk counts after rebuild. Differences usually mean parsing or source mapping changed what chunks were available.

## Cross-Platform Checklist

Use this checklist for each transfer target.

### Source Host

- Run `uv run pytest tests/integration/test_export_bundle_api.py` before relying on a new bundle behavior.
- Export with source files included unless the target has the same source files available.
- Record required models from Export Center or `manifest.json`.
- Store the ZIP outside Git.

### Target Host: macOS

- Install Python 3.11, `uv`, Node.js 22 or newer, Docker Desktop, and Ollama.
- Run `uv sync --all-extras --dev`.
- Run `uv run alembic upgrade head`.
- Start Qdrant with `docker compose up -d qdrant` if vector rebuilds will use the real Qdrant service.
- Pull or cache required local models, including `gemma3:4b` for default chat when needed.
- Validate the ZIP in Recreate Repository before running recreate.

### Target Host: Windows-Native Python/Ollama

- Use Windows-native Python 3.11 and `uv`; do not rely on WSL path semantics for native app runs.
- Install Node.js 22 or newer, Docker Desktop, and Ollama for Windows.
- Keep source mappings as Windows paths in the UI, but rely on SHA-256 matching rather than original absolute paths.
- Run `uv sync --all-extras --dev` and `uv run alembic upgrade head`.
- Start Qdrant through Docker Desktop before real vector rebuild checks.
- Validate first; resolve missing source mappings and model warnings before recreate.

### Target Host: Linux/Ubuntu

- Install Python 3.11, `uv`, Node.js 22 or newer, Docker Engine or Docker Desktop, and Ollama.
- Run `uv sync --all-extras --dev`.
- Run `uv run alembic upgrade head`.
- Start Qdrant with `docker compose up -d qdrant`.
- Ensure mapped source files are readable by the app process.
- Validate first, then recreate.

## Deterministic And Live Checks

Default deterministic checks:

```bash
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
cd frontend
npm run build
npm test
```

PowerShell:

```powershell
uv run ruff format --check .
uv run ruff check .
uv run mypy src tests
uv run pytest
Set-Location frontend
npm run build
npm test
Set-Location ..
```

PRD9-focused deterministic checks:

```bash
uv run pytest tests/unit/test_export_bundle.py tests/integration/test_export_bundle_api.py
cd frontend
npm test
```

PowerShell:

```powershell
uv run pytest tests/unit/test_export_bundle.py tests/integration/test_export_bundle_api.py
Set-Location frontend
npm test
Set-Location ..
```

Optional live checks when local services and models are available:

```bash
docker compose up -d qdrant
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_vector_live.py
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_ollama_live.py
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_chat_rag_live.py
```

PowerShell:

```powershell
docker compose up -d qdrant
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live tests/integration/test_vector_live.py
uv run pytest -m live tests/integration/test_ollama_live.py
uv run pytest -m live tests/integration/test_chat_rag_live.py
Remove-Item Env:\RUN_LIVE_TESTS
```

Live cross-encoder checks require the configured cross-encoder in the local SentenceTransformers cache:

```bash
uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"
RUN_LIVE_TESTS=1 uv run pytest -m live tests/integration/test_cross_encoder_live.py
```

PowerShell:

```powershell
uv run python -c "from sentence_transformers import CrossEncoder; CrossEncoder('cross-encoder/ms-marco-MiniLM-L6-v2')"
$env:RUN_LIVE_TESTS = "1"
uv run pytest -m live tests/integration/test_cross_encoder_live.py
Remove-Item Env:\RUN_LIVE_TESTS
```

Manual cross-platform transfer remains a review checklist item unless each target OS is available during the review window.

## Clean Environment Reset

Use Repository Administration before manual deletion. The app can preview one-repository deletion or clear-all cleanup, require explicit confirmation, remove repository-scoped database records and app-managed artifacts, preserve external source files and model caches, and recreate the default repository after clear-all.

Before destructive cleanup, export anything you may need to keep:

1. Open Export Center for the repository.
2. Create a portable ZIP with source files included when redistribution is allowed.
3. Store the ZIP outside `data/`, `exports/`, and other app-managed cleanup targets.

In-app reset path:

1. Open Repository Administration.
2. Use **Preview cleanup** for one repository or **Preview clear all** for local transfer testing.
3. Review database records, app-managed files, full-text/vector indexes, external files, export metadata, chat/retrieval history, sandbox history, and model-cache preservation.
4. Type the required confirmation value and run the cleanup.
5. If Qdrant was unavailable, start Qdrant and use **Retry vector cleanup** from the cleanup result. This removes the leftover collection without deleting the repository again.

Preservation defaults:

- External source files referenced from outside app-managed storage are preserved.
- Ollama, SentenceTransformers, and reranker model caches are preserved by default.
- Export ZIPs should be treated as backups; keep them outside cleanup targets if you need them after reset.

Manual fallback is only for a broken local development environment where the app cannot start. Stop the backend, frontend, workers, and Qdrant first.

macOS/Linux or Git Bash fallback:

```bash
docker compose down
rm -rf data exports .qdrant
docker volume prune
uv run alembic upgrade head
```

Windows PowerShell fallback:

```powershell
docker compose down
Remove-Item -Recurse -Force .\data, .\exports, .\.qdrant -ErrorAction SilentlyContinue
docker volume prune
uv run alembic upgrade head
```

Only remove `models/` if you intentionally want to delete model files managed inside the workspace. Ollama and SentenceTransformers commonly store model caches outside this repository, so resetting repo data does not remove those downloads.

Safe cleanup tests use temporary data directories, test databases, and fake vector stores. Do not point cleanup tests at a real research workspace or shared Qdrant instance unless you intentionally created disposable collections for that run.
