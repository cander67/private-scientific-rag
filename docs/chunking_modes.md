# Chunking Modes and Tokenizers

Repository chunking settings control how parsed document text is split before full-text indexing, vector embedding, retrieval, chat, and export/recreate snapshots. Changing chunking or parser settings affects future processing and should be treated as a document reprocessing change for existing content.

## Chunking Modes

`recursive` is the default general-purpose mode. It tries to keep nearby text together while respecting the configured chunk size and overlap. Use it when you want stable, readable chunks for mixed scientific PDFs, Markdown, text files, and patent-like documents.

`fixed` is the simplest mode. It splits text into fixed-size windows with the configured overlap. Use it when repeatability is more important than preserving section-like boundaries.

`semantic` is reserved for a more structure-aware path. Until a dedicated semantic chunking implementation is promoted, treat it as an explicit experimental setting that should be verified with source inspection and retrieval checks before relying on it for a corpus.

## Parser Relationship

Parser settings decide what text and structure are available before chunking. Chunking settings decide how that parsed text becomes retrievable units. Changing either parser or chunking defaults should prompt document reprocessing, then full-text/vector rebuilds, before search and chat are considered fresh.

PRD26 will replace parser free-text fields with fixed choices plus `Auto`. `Auto` is intended to preserve a stable user-facing setting while allowing the app to improve parser-selection logic later.

## Tokenizers

Current full-text tokenizer choices are `unicode61` and `porter`.

`unicode61` is the default SQLite FTS5 tokenizer and is a good baseline for exact terms, formulas, identifiers, and mixed scientific text.

`porter` adds stemming behavior that can improve matches across related English word forms, but it may be less predictable for formulas, abbreviations, identifiers, and technical symbols.

Broader tokenizer expansion should wait for corpus-specific retrieval evidence, because tokenizer changes affect sparse search behavior and can make existing full-text indexes stale.
