# PRD 31: Custom Domain Tokenizers

**Status:** Backlog.

## Problem Statement

PRD30 makes chunking token-aware, but it still depends on tokenizers that come from supported embedding model families or runtime providers. That is the right default for retrieval correctness, because chunks should usually be measured with the same tokenizer family as the embedding or chat model consuming them.

Some technical corpora have vocabulary that tokenizes poorly with general-purpose model tokenizers. Materials formulas, chemical identifiers, patent claim notation, instrument parameters, mathematical symbols, source-code-like strings, part numbers, and OCR artifacts can be split into many small subword tokens. That can make chunks shorter than expected, produce awkward boundaries inside domain terms, and make tokenizer behavior hard to audit for specialized collections.

The app needs a future path for researchers to train, register, inspect, evaluate, and select custom tokenizers for unique technical vocabularies without weakening the default model-aligned tokenizer strategy from PRD30.

## Solution

Add a custom tokenizer workflow that treats user-trained tokenizers as explicit, repository-scoped advanced assets.

Researchers should be able to create a tokenizer from a selected local corpus or imported tokenizer directory, inspect vocabulary examples, compare token counts against the active model tokenizer and regex fallback, run retrieval-quality checks before adopting it, and then select it deliberately for chunking. Custom tokenizer selection should be fingerprinted, exported/recreated where possible, and treated as reprocessing-relevant.

Hugging Face's `tokenizers` and `transformers` stack should be the primary implementation path. Custom tokenizers should be saved in a local `save_pretrained`-compatible directory so they can be loaded through `AutoTokenizer` or a compatible tokenizer backend. The product should prefer trainable/custom HuggingFace tokenizers over ad hoc token splitting rules because they provide a standard vocabulary, merge/config files, serialization format, and offset-mapping support when backed by fast tokenizers.

This PRD should not make custom tokenizers the default. It should make them auditable, testable, reversible, and clearly marked as an advanced retrieval experiment.

## User Stories

1. As a researcher, I want to train a tokenizer on a technical corpus, so that recurring domain terms are not split unpredictably.
2. As a researcher, I want to import an existing HuggingFace-compatible tokenizer directory, so that I can reuse tokenizers created outside the app.
3. As a researcher, I want to preview how domain strings tokenize under the active model tokenizer, custom tokenizer, and regex fallback, so that I can understand the tradeoff before adopting it.
4. As a researcher, I want custom tokenizer metadata recorded on chunks and parser fingerprints, so that repository behavior remains reproducible.
5. As a researcher, I want changing the custom tokenizer to mark documents stale, so that old chunks are not mixed with newly tokenized chunks.
6. As a researcher, I want export/recreate bundles to include custom tokenizer references or clear missing-tokenizer warnings, so that portability limits are visible.
7. As a maintainer, I want custom tokenizers behind a small service boundary, so that training, loading, previewing, and chunking can be tested independently.
8. As a maintainer, I want default CI to use tiny deterministic tokenizer fixtures, so that tests do not require large corpora or network downloads.
9. As a researcher, I want retrieval evaluation guidance before promoting a custom tokenizer, so that a smaller token count does not get mistaken for better retrieval quality.
10. As a maintainer, I want custom tokenizer storage to fit the local storage/housekeeping model, so that generated tokenizer assets can be inspected and cleaned later.
11. As a researcher, I want clear warnings when a custom tokenizer no longer matches the embedding model's native tokenizer, so that I understand it may improve chunk boundaries while diverging from model token budgeting.

## Implementation Decisions

- Keep PRD30's `auto` tokenizer behavior as the default.
- Add custom tokenizers as an advanced manual tokenizer source, not as automatic replacements for model-aligned tokenizers.
- Use HuggingFace-compatible tokenizer directories as the persistence format whenever possible.
- Prefer fast tokenizers with offset mappings. If a custom tokenizer lacks offset support, the app should block it for chunking or clearly fall back to a safe source-span strategy.
- Store custom tokenizer assets under repository-managed local data storage, not in Git by default.
- Add metadata for tokenizer ID, display name, source corpus or import path, training algorithm/config, vocabulary size, created timestamp, content hash, implementation library, offset support, and precision/experimental status.
- Include custom tokenizer identity and content hash in parser/chunk fingerprints.
- Require document reprocessing and full-text/vector rebuild guidance after adopting or changing a custom tokenizer.
- Add tokenizer preview and comparison before adoption. Suggested examples should include formulas, identifiers, OCR-like strings, ordinary prose, and non-English text when present in the corpus.
- Add retrieval evaluation guidance before promotion. Custom tokenizer adoption should be framed as an experiment that needs source inspection and retrieval checks.
- Coordinate with PRD24 for storage provenance/housekeeping and PRD18 for evidence-backed evaluation if broader promotion criteria are needed.

## Testing Decisions

- Unit tests should cover custom tokenizer registration, metadata validation, fingerprint changes, preview tokenization, unsupported tokenizer rejection, and fallback warnings.
- Use tiny deterministic tokenizer fixtures in default tests rather than downloading model or tokenizer assets.
- Integration tests should verify upload/reprocess records custom tokenizer metadata on chunks and document versions.
- Export/recreate tests should verify custom tokenizer metadata is preserved and missing custom tokenizer assets are reported clearly.
- Frontend contract tests should cover custom tokenizer preview, selection warnings, stale-impact copy, and Source Viewer metadata display.
- Optional live/manual tests may train a small tokenizer from a representative local technical corpus, but this must not become a default CI requirement.

## Out of Scope

- Automatically fine-tuning embedding or chat models to match a custom tokenizer.
- Making custom tokenizers the default for new repositories.
- Downloading large external corpora or tokenizer assets during default CI.
- Replacing SQLite FTS5 tokenizers such as `unicode61` or `porter`.
- Full multimodal image-token budgeting for vision-language prompts.
- Guaranteeing retrieval-quality improvement from a custom tokenizer without evaluation evidence.

## Further Notes

- Custom tokenizers can make chunk boundaries more domain-friendly while becoming less aligned with the embedding model's native tokenizer. The UI and docs should state that tradeoff plainly.
- A good first implementation should support importing a saved HuggingFace-compatible tokenizer before adding in-app training, because import validates the storage, metadata, preview, chunking, and export/recreate path with less product surface.
- A later phase can add in-app training from selected repository documents using `train_new_from_iterator` or the lower-level `tokenizers` library once corpus selection and evaluation workflows are clear.
