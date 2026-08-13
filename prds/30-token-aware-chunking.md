# PRD 30: Token-Aware Chunking

**Status:** Implemented through phase 6. Reopened for scoped tokenizer-strategy remediation: remove `tiktoken` from current vector/embedding chunk-tokenizer settings, prefer HuggingFace/Transformers tokenizers for local model families, add feature-detected Ollama runtime tokenizer support when available, and document true multimodal image-token budgeting as follow-up scope.

## Problem Statement

Document chunking is currently controlled by character counts. That is simple and deterministic, but it does not match the limits that matter most for retrieval-augmented generation: embedding models and chat models consume tokens, not characters.

For scientific and patent-like corpora, character counts can diverge sharply from model token counts. Dense formulas, chemical names, tables, OCR artifacts, symbols, identifiers, non-English text, and whitespace-heavy parser output can all make an 800-character chunk much shorter or longer than expected in model terms. This creates avoidable uncertainty: chunks may be too small for useful context, too large for embedding limits, or uneven across corpora and embedding models.

The project is still early enough that backwards compatibility with existing character-based chunk settings and persisted chunks is not required. This PRD should replace the default chunk-sizing unit with tokens and make tokenizer behavior explicit, reproducible, and visible in chunk metadata.

## Solution

Implement token-aware chunking as the default ingestion behavior.

For SentenceTransformers embedding models, chunking should use the selected model's HuggingFace tokenizer through `transformers` when it can be loaded reliably. For Ollama embedding models, chunking should prefer Ollama's own model-aligned tokenization endpoint when the local runtime exposes it, because that is the closest available match to the model actually serving embeddings. If the runtime endpoint is unavailable, known Ollama embedding models may use registry-declared tokenizer metadata that points at a real HuggingFace tokenizer implementation when one is known. When exact tokenizer access is unavailable, the app should use a clearly identified fallback tokenizer rather than silently pretending to be exact. Chunk metadata should record the tokenizer provider, tokenizer ID, tokenizer name, implementation library, tokenizer source, selection mode, precision, chunk size, overlap, and unit used to produce every chunk.

`tiktoken` should not be exposed as a current vector/embedding chunk-tokenizer choice unless an OpenAI-compatible embedding or chat-provider PRD makes OpenAI-style budgeting first-class. Keeping it in the current settings surface would invite mismatches between the tokenizer selected for chunking and the local embedding model used for vector search.

Recursive chunking should preserve parser segment boundaries where possible while measuring size and overlap in tokens. Fixed chunking should create token windows rather than character windows. Oversized parser segments should be split in a token-aware way so no single segment can bypass the configured chunk size.

Settings, source inspection, export/recreate, stale-index impact analysis, and documentation should describe token-based chunking as the current default. Because backwards compatibility is not required at this stage, the implementation may update schemas, fixtures, and tests directly rather than preserving old character semantics.

PRD30 is still a text-chunking PRD. It applies to parsed text, OCR-recovered text, and other text extracted from documents or images. It does not provide full multimodal prompt budgeting for vision-language models: image placeholder tokens, model-specific image-token expansion, chat templates containing image parts, and per-image context limits should be handled by a later multimodal context-packing PRD.

## User Stories

1. As a researcher, I want chunk size and overlap to be measured in tokens, so that chunk settings match embedding and chat model behavior more closely.
2. As a researcher, I want SentenceTransformers chunking to use the active embedding model's tokenizer, so that chunk boundaries reflect the model used for vector search.
3. As a researcher, I want Ollama embedding chunking to declare whether it used an exact library-backed tokenizer or the approximate regex fallback, so that I can understand how precise the chunk sizing is.
4. As a researcher, I want chunk metadata to record tokenizer details, so that source inspection, export/recreate, and debugging can explain how chunks were produced.
5. As a researcher, I want recursive chunking to keep readable parser-derived segment boundaries where possible, so that chunks remain inspectable and citation-friendly.
6. As a researcher, I want fixed chunking to produce deterministic token windows, so that repeatable chunk boundaries are available when I need them.
7. As a researcher, I want very long parser segments to be split safely, so that a single long table, OCR block, or paragraph does not exceed the configured token budget.
8. As a researcher, I want settings impact analysis to treat tokenizer, chunk size, overlap, mode, and embedding model changes as reprocessing-relevant, so that stale chunks are not mistaken for fresh chunks.
9. As a researcher, I want Settings / Models to show token-based chunking controls and resolved tokenizer metadata, so that chunking behavior is not hidden behind implementation details.
10. As a researcher, I want export/recreate bundles to include token chunking metadata, so that repositories can be audited or recreated with the same tokenization assumptions.
11. As a maintainer, I want token counting and token-window splitting behind a small service boundary, so that model-specific tokenizer behavior can be tested without rewriting ingestion.
12. As a maintainer, I want deterministic tests for tokenizer resolution, recursive token coalescing, fixed token windows, oversized segment splitting, metadata recording, and stale-setting detection.
13. As a maintainer, I want fallback tokenizer behavior to be explicit and testable, so that unsupported or custom Ollama models do not create misleading chunk metadata.
14. As a maintainer, I want documentation to explain that tokenizer choice is part of retrieval behavior, so that future model changes can be evaluated deliberately.
15. As a researcher, I want to see the actual tokenizer library and tokenizer identifier used for chunking, so that a fallback regex splitter is not confused with a model tokenizer.
16. As a researcher, I want to select from supported chunk tokenizers when automatic resolution is not what I need, so that advanced workflows can align chunking with a known tokenizer family deliberately.
17. As a maintainer, I want tokenizer names to be descriptive and library-backed wherever possible, so that registry entries are auditable rather than opaque labels.
18. As a researcher, I want Ollama embedding chunking to use Ollama's own tokenizer when the installed runtime supports it, so that token counts match the local model more closely than registry guesses or regex fallback.
19. As a maintainer, I want unsupported tokenizer endpoints to degrade cleanly to registry/HuggingFace/fallback paths, so that default tests and older Ollama installs remain deterministic.
20. As a researcher, I want unsupported OpenAI-style tokenizer choices hidden from current embedding settings, so that I do not accidentally chunk for a tokenizer family that is not powering my vector index.
21. As a maintainer, I want PRD30 to state clearly that text chunking is not full image-token budgeting for multimodal chat, so that image support gets designed at the correct model interface.

## Implementation Decisions

- Replace character-count chunk sizing with token-count chunk sizing as the default behavior.
- Do not preserve backwards compatibility for existing character-based chunk settings or old persisted chunk metadata.
- Add a tokenizer resolution boundary that accepts repository embedding settings and returns a tokenizer implementation plus metadata about tokenizer source and precision.
- Use the selected SentenceTransformers model tokenizer for `sentence_transformers` providers when available.
- Add a tokenizer catalog that exposes `auto`, HuggingFace/SentenceTransformers tokenizers, known Ollama runtime/registry mappings, and the explicit regex fallback.
- Do not expose `tiktoken` as a current vector/embedding chunk-tokenizer choice. Defer OpenAI-compatible encodings until an OpenAI-compatible provider PRD makes those models part of the supported runtime surface.
- Extend the tokenizer resolver with a feature-detected Ollama runtime tokenizer path. If `/api/tokenize` is available for the selected local model, treat it as the preferred exact Ollama tokenizer and record runtime metadata. If unavailable, fall back to registry-declared HuggingFace mappings where known, then the explicit regex fallback.
- Extend the embedding model registry with tokenizer metadata for known Ollama embedding models. Registry entries should map to a real HuggingFace tokenizer implementation where known; only use fallback metadata when no exact tokenizer is available.
- Use a deterministic app-level regex fallback tokenizer for unknown or unsupported tokenizer selections, and record that fallback in chunk metadata. Keep `private-rag/simple-token-fallback-v1`, but label it as an approximate regex fallback, not a model tokenizer.
- Allow manual chunk-tokenizer selection from the supported tokenizer catalog. `auto` should remain the default and should be recommended; manual choices should be stored in repository settings, included in parser/chunk fingerprints, and surfaced as reprocessing-relevant. Manual choices should be limited to supported local model tokenizers and the explicit fallback until additional provider PRDs expand the model surface.
- Keep `recursive` and `fixed` chunking modes, but reinterpret `chunk_size` and `chunk_overlap` as token counts.
- Keep `semantic` reserved unless this PRD explicitly implements a separate semantic chunker; until then, it should not claim model-semantic boundary detection.
- Preserve citation/source-navigation metadata by mapping token windows back to character spans, line ranges, page ranges, and parser sections as accurately as possible.
- Split oversized parser segments token-aware before or during coalescing so chunk-size limits remain meaningful.
- Include tokenizer metadata in parser/chunk settings fingerprints so tokenizer changes make parsed chunks stale.
- Update Settings / Models, source inspection, export/recreate manifests, and chunking documentation to use token vocabulary.

## Testing Decisions

- Unit tests should focus on external chunking behavior: chunk token budgets, overlap semantics, metadata, source spans, and stale-setting detection.
- Tokenizer resolution should be tested with fake tokenizer implementations so deterministic CI does not depend on downloading model weights.
- SentenceTransformers tokenizer integration should be covered by a mocked or locally fake model boundary in default tests, with optional live coverage only if local models are available.
- Tests should verify `tiktoken` is not exposed as a current vector/embedding tokenizer choice unless a future OpenAI-compatible provider PRD reintroduces it deliberately.
- Ollama tokenizer tests should cover feature-detected runtime tokenization where available, unsupported endpoint fallback, known-model registry mappings to HuggingFace tokenizers where available, custom model fallback, and metadata that distinguishes exact versus fallback tokenization.
- Manual tokenizer selection tests should cover settings validation, settings impact/reprocess freshness, chunk metadata, Source Viewer display, export/recreate payloads, and warnings when a selected tokenizer does not match the embedding model.
- Ingestion tests should verify recursive token coalescing preserves parser segment boundaries where possible and splits oversized segments when needed.
- Ingestion tests should verify fixed token windows produce deterministic overlap and stable source spans.
- API or integration tests should verify upload/reprocess records token chunk metadata and settings fingerprints.
- Export/recreate tests should verify token chunking metadata and settings survive bundle creation and recreate validation.
- Frontend contract tests should verify Settings / Models labels, chunking controls, impact copy, and Source Viewer chunk metadata use token terminology.
- Documentation tests are not required, but docs should be updated alongside behavior so manual testing has an accurate reference.

## Out of Scope

- A fully semantic chunking algorithm based on embedding similarity, document layout intelligence, or LLM boundary selection.
- Exact tokenizer support for every possible custom Ollama model.
- Optimizing chunk size automatically from corpus statistics or retrieval evaluation.
- Supporting both character and token chunking modes as a compatibility feature.
- Immutable multi-index comparison or preserving old character-based vector indexes.
- Changing SQLite FTS5 tokenizers such as `unicode61` or `porter`.
- Changing chat prompt context packing beyond making retrieved chunk sizes more predictable.
- Downloading tokenizer assets during default CI. Library-backed tokenizers that need model files must use local cache by default and report unavailable state clearly.
- Full multimodal vision-language context budgeting, including image-token accounting and image-part chat-template packing.
- Training, registering, evaluating, or deploying custom domain tokenizers for technical vocabularies. That is deferred to PRD31.

## Further Notes

- Implemented default chunking uses a 512-token chunk size and 64-token overlap.
- Phase 6 remediation replaced opaque tokenizer labels with a visible tokenizer catalog and library-backed tokenizer choices.
- The next tokenizer remediation should remove `tiktoken` from the current settings/catalog surface, because current vector embeddings are local SentenceTransformers/Ollama rather than OpenAI-compatible providers.
- The tokenizer stack should prefer exact local-runtime or library tokenizers, then known registry mappings to library tokenizers, then the explicit regex fallback.
- If exact tokenizer access is unavailable for an Ollama model, the fallback tokenizer is visible in settings guidance, parser fingerprints, persisted chunk metadata, export bundles, and recreate validation.
- Because chunking changes affect every downstream index, Settings / Models, freshness metadata, and docs make the required reprocess and full-text/vector rebuild path explicit.
- Deterministic verification covers tokenizer resolution, recursive token coalescing, fixed token windows, oversized segment splitting, upload/reprocess metadata, export/recreate validation, frontend contract surfaces, and calibrated fixture behavior. Live SentenceTransformers cache and Ollama runtime checks remain opt-in because they depend on local host state.
