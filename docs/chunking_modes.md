# Chunking Modes and Tokenizers

Repository chunking settings control how parsed document text is split before full-text indexing, vector embedding, retrieval, chat, and export/recreate snapshots. Changing chunking or parser settings affects future processing and should be treated as a document reprocessing change for existing content.

Chunk size and overlap are token counts. The default is a 512-token chunk size with 64-token overlap. That budget is large enough to keep most short scientific sections, Markdown blocks, and parser-derived procedure segments readable while still staying comfortably below local embedding-model context limits. Increase it when long-form narrative context is being split too aggressively; decrease it when retrieval results feel too broad or unrelated facts are being bundled together. The settings API records this as `chunk_unit: "tokens"` so source inspection, parser fingerprints, and export/recreate manifests can identify the sizing unit that produced a chunk.

## Chunking Modes

`recursive` is the default general-purpose mode. It keeps parser-derived segments together while they fit inside the configured token size, carries overlap by token budget, and splits oversized parser segments into token windows. Use it when you want stable, readable chunks for mixed scientific PDFs, Markdown, text files, and patent-like documents.

`fixed` is the simplest mode. It splits text into fixed-size token windows with the configured overlap. Use it when repeatability is more important than preserving section-like boundaries.

`semantic` is reserved for a more structure-aware path. Until a dedicated semantic chunking implementation is promoted, treat it as an explicit experimental setting that should be verified with source inspection and retrieval checks before relying on it for a corpus.

## Parser Relationship

Parser settings decide what text and structure are available before chunking. Chunking settings decide how that parsed text becomes retrievable units. Saved parser and chunking settings are applied during upload and explicit reprocess. Changing either parser or chunking defaults should prompt document reprocessing, then full-text/vector rebuilds, before search and chat are considered fresh.

Parser settings use catalog-backed choices plus `Auto`. `Auto` preserves a stable user-facing setting while allowing the app to improve parser-selection logic later. Source Viewer shows parser names and routes first; raw package version numbers are dependency details.

## Tokenizers

Chunking tokenizers default to `auto`, which resolves from repository embedding settings. SentenceTransformers embedding models use their HuggingFace tokenizer through `transformers` when it is available locally. Ollama embedding models use the local Ollama runtime tokenizer when that endpoint is available for the selected model; otherwise known Ollama embedding models use registry-declared tokenizer metadata. When an exact tokenizer mapping is not available, the registry names `private-rag/simple-token-fallback-v1` as an approximate fallback instead of labeling the count as exact.

Settings / Models exposes manual tokenizer IDs for advanced users. Current catalog-backed IDs include `hf:sentence-transformers/all-MiniLM-L6-v2`, `hf:sentence-transformers/all-mpnet-base-v2`, and `private-rag/simple-token-fallback-v1`. HuggingFace entries require the model tokenizer to be cached locally; the fallback regex tokenizer counts word-like runs plus individual punctuation/symbol tokens. OpenAI-style encodings are not exposed as current vector/embedding chunk-tokenizer choices because the active embedding providers are local SentenceTransformers and Ollama.

This token chunking path applies to parsed text, OCR-recovered text, and other text extracted from documents or images. It does not account for image tokens in multimodal chat prompts, image placeholder expansion, or model-specific image-part chat templates.

Every parsed version fingerprint and generated chunk records tokenizer metadata: provider, tokenizer ID, tokenizer name, implementation library, tokenizer source, precision, selection mode, offset support, fallback status, and any fallback reason. Changing the embedding provider/model, manual tokenizer mode/ID, chunk mode, chunk size, or overlap makes existing parsed chunks stale and requires document reprocessing before indexes are fresh again.

Export/recreate bundles include these tokenizer details in document-version fingerprints and chunk payloads. Bundle validation reports the recorded tokenizer ID and implementation library, warns when fallback tokenizers were used, and warns when chunk tokenizer metadata does not match its version fingerprint.

Full-text search has a separate SQLite FTS tokenizer setting. Current full-text tokenizer choices are `unicode61` and `porter`.

`unicode61` is the default SQLite FTS5 tokenizer and is a good baseline for exact terms, formulas, identifiers, and mixed scientific text.

`porter` adds stemming behavior that can improve matches across related English word forms, but it may be less predictable for formulas, abbreviations, identifiers, and technical symbols.

Broader tokenizer expansion should wait for corpus-specific retrieval evidence, because tokenizer changes affect sparse search behavior and can make existing full-text indexes stale.
