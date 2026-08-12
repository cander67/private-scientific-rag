# Chunking Modes and Tokenizers

Repository chunking settings control how parsed document text is split before full-text indexing, vector embedding, retrieval, chat, and export/recreate snapshots. Changing chunking or parser settings affects future processing and should be treated as a document reprocessing change for existing content.

Chunk size and overlap are token counts. The settings API records this as `chunk_unit: "tokens"` so source inspection, parser fingerprints, and export/recreate manifests can identify the sizing unit that produced a chunk.

## Chunking Modes

`recursive` is the default general-purpose mode. It tries to keep nearby text together while respecting the configured token size and token overlap. Use it when you want stable, readable chunks for mixed scientific PDFs, Markdown, text files, and patent-like documents.

`fixed` is the simplest mode. It splits text into fixed-size token windows with the configured overlap. Use it when repeatability is more important than preserving section-like boundaries.

`semantic` is reserved for a more structure-aware path. Until a dedicated semantic chunking implementation is promoted, treat it as an explicit experimental setting that should be verified with source inspection and retrieval checks before relying on it for a corpus.

## Parser Relationship

Parser settings decide what text and structure are available before chunking. Chunking settings decide how that parsed text becomes retrievable units. Saved parser and chunking settings are applied during upload and explicit reprocess. Changing either parser or chunking defaults should prompt document reprocessing, then full-text/vector rebuilds, before search and chat are considered fresh.

Parser settings use catalog-backed choices plus `Auto`. `Auto` preserves a stable user-facing setting while allowing the app to improve parser-selection logic later. Source Viewer shows parser names and routes first; raw package version numbers are dependency details.

## Tokenizers

Chunking tokenizers are resolved from the repository embedding settings. SentenceTransformers embedding models use the selected model tokenizer when it is available locally. Known Ollama embedding models use registry-declared tokenizer metadata; when exact tokenizer access is unavailable, the app records an explicit fallback tokenizer instead of labeling the count as exact.

Every parsed version fingerprint and generated chunk records tokenizer metadata: provider, tokenizer name, tokenizer source, precision, and any fallback reason. Changing the embedding provider/model, tokenizer metadata, chunk mode, chunk size, or overlap makes existing parsed chunks stale and requires document reprocessing before indexes are fresh again.

Full-text search has a separate SQLite FTS tokenizer setting. Current full-text tokenizer choices are `unicode61` and `porter`.

`unicode61` is the default SQLite FTS5 tokenizer and is a good baseline for exact terms, formulas, identifiers, and mixed scientific text.

`porter` adds stemming behavior that can improve matches across related English word forms, but it may be less predictable for formulas, abbreviations, identifiers, and technical symbols.

Broader tokenizer expansion should wait for corpus-specific retrieval evidence, because tokenizer changes affect sparse search behavior and can make existing full-text indexes stale.
