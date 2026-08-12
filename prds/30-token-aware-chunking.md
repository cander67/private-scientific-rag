# PRD 30: Token-Aware Chunking

**Status:** Next planned implementation item.

## Problem Statement

Document chunking is currently controlled by character counts. That is simple and deterministic, but it does not match the limits that matter most for retrieval-augmented generation: embedding models and chat models consume tokens, not characters.

For scientific and patent-like corpora, character counts can diverge sharply from model token counts. Dense formulas, chemical names, tables, OCR artifacts, symbols, identifiers, non-English text, and whitespace-heavy parser output can all make an 800-character chunk much shorter or longer than expected in model terms. This creates avoidable uncertainty: chunks may be too small for useful context, too large for embedding limits, or uneven across corpora and embedding models.

The project is still early enough that backwards compatibility with existing character-based chunk settings and persisted chunks is not required. This PRD should replace the default chunk-sizing unit with tokens and make tokenizer behavior explicit, reproducible, and visible in chunk metadata.

## Solution

Implement token-aware chunking as the default ingestion behavior.

For SentenceTransformers embedding models, chunking should use the selected model's tokenizer when it can be loaded reliably. For known Ollama embedding models, chunking should use a registry-declared tokenizer strategy. When exact tokenizer access is unavailable, the app should use a clearly identified fallback tokenizer rather than silently pretending to be exact. Chunk metadata should record the tokenizer provider, tokenizer name, tokenizer source, chunk size, overlap, and unit used to produce every chunk.

Recursive chunking should preserve parser segment boundaries where possible while measuring size and overlap in tokens. Fixed chunking should create token windows rather than character windows. Oversized parser segments should be split in a token-aware way so no single segment can bypass the configured chunk size.

Settings, source inspection, export/recreate, stale-index impact analysis, and documentation should describe token-based chunking as the current default. Because backwards compatibility is not required at this stage, the implementation may update schemas, fixtures, and tests directly rather than preserving old character semantics.

## User Stories

1. As a researcher, I want chunk size and overlap to be measured in tokens, so that chunk settings match embedding and chat model behavior more closely.
2. As a researcher, I want SentenceTransformers chunking to use the active embedding model's tokenizer, so that chunk boundaries reflect the model used for vector search.
3. As a researcher, I want Ollama embedding chunking to declare whether it used an exact or fallback tokenizer strategy, so that I can understand how precise the chunk sizing is.
4. As a researcher, I want chunk metadata to record tokenizer details, so that source inspection, export/recreate, and debugging can explain how chunks were produced.
5. As a researcher, I want recursive chunking to keep readable parser-derived segment boundaries where possible, so that chunks remain inspectable and citation-friendly.
6. As a researcher, I want fixed chunking to produce deterministic token windows, so that repeatable chunk boundaries are available when I need them.
7. As a researcher, I want very long parser segments to be split safely, so that a single long table, OCR block, or paragraph does not exceed the configured token budget.
8. As a researcher, I want settings impact analysis to treat tokenizer, chunk size, overlap, mode, and embedding model changes as reprocessing-relevant, so that stale chunks are not mistaken for fresh chunks.
9. As a researcher, I want Settings / Models to show token-based chunking controls and tokenizer strategy, so that chunking behavior is not hidden behind implementation details.
10. As a researcher, I want export/recreate bundles to include token chunking metadata, so that repositories can be audited or recreated with the same tokenization assumptions.
11. As a maintainer, I want token counting and token-window splitting behind a small service boundary, so that model-specific tokenizer behavior can be tested without rewriting ingestion.
12. As a maintainer, I want deterministic tests for tokenizer resolution, recursive token coalescing, fixed token windows, oversized segment splitting, metadata recording, and stale-setting detection.
13. As a maintainer, I want fallback tokenizer behavior to be explicit and testable, so that unsupported or custom Ollama models do not create misleading chunk metadata.
14. As a maintainer, I want documentation to explain that tokenizer choice is part of retrieval behavior, so that future model changes can be evaluated deliberately.

## Implementation Decisions

- Replace character-count chunk sizing with token-count chunk sizing as the default behavior.
- Do not preserve backwards compatibility for existing character-based chunk settings or old persisted chunk metadata.
- Add a tokenizer resolution boundary that accepts repository embedding settings and returns a tokenizer implementation plus metadata about tokenizer source and precision.
- Use the selected SentenceTransformers model tokenizer for `sentence_transformers` providers when available.
- Extend the embedding model registry with tokenizer strategy metadata for known Ollama embedding models.
- Use a deterministic app-level fallback tokenizer for unknown or unsupported Ollama tokenizer strategies, and record that fallback in chunk metadata.
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
- Ollama tokenizer strategy tests should cover known-model registry metadata, fallback behavior, custom model fallback, and metadata that distinguishes exact versus fallback tokenization.
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

## Further Notes

- The first implementation should prefer correctness and inspectability over broad tokenizer coverage.
- If exact tokenizer access is unavailable for an Ollama model, the fallback tokenizer should be visible in settings/readiness metadata and persisted chunk metadata.
- Because chunking changes affect every downstream index, implementation should make the required reprocess and full-text/vector rebuild path obvious.
- Default chunk-size values should be reconsidered during implementation because the current defaults were chosen as character counts, not token counts.
