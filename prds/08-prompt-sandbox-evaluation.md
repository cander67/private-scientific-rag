# PRD 8: Prompt Sandbox

## Goal

Create a controlled space to compare prompts, search settings, rerankers, and models before changing normal chat behavior.

## User Stories

- As a researcher, I can test prompts without changing normal chat defaults.
- As a researcher, I can compare the same query across retrieval modes and rerankers.
- As a researcher, I can inspect each run's retrieved context, generated answer, latency, and status side by side.

## Scope

- Prompt template/version model.
- Prompt Sandbox UI.
- Retrieved context preview.
- Side-by-side run comparison.
- Progressive comparison execution so each retrieval mode appears as soon as it finishes.
- Prompt version save, copy, and delete workflows.
- Persisted sandbox run history with prompt snapshots, retrieval settings, local model, retrieved context, answer, citations, latency, and status.
- Explicit separation from normal chat defaults.

## Acceptance Criteria

- Same query can be run across full-text, vector, hybrid, and reranked hybrid.
- Prompt versions are saved and associated with runs.
- Each retrieval mode output appears as soon as it is available during a comparison.
- Run cards show retrieved context, generated answer, model, settings, citations, status/errors, and latency in seconds.
- Prompt versions can be deleted from the sandbox without changing normal chat defaults or rewriting completed run history.
- Sandbox actions do not mutate repository chat defaults.
- The production React UI exposes the Prompt Sandbox as a first-class workspace.

## Test Plan

- Unit test prompt versioning.
- Integration test side-by-side run persistence.
- Integration test progressive comparison execution and prompt deletion.
- Frontend contract tests for prompt save/delete, comparison execution, running state, context preview, and persisted comparison reload.

## Documentation References

- `tests/README.md` for test and golden corpus conventions.
- Elastic semantic relevance tuning: https://www.elastic.co/search-labs/blog/search-relevance-tuning-in-semantic-search
- Azure Search relevance overview: https://learn.microsoft.com/en-us/azure/search/search-relevance-overview
- SentenceTransformers evaluation documentation: https://sbert.net/docs/sentence_transformer/usage/evaluation.html

## Deferred Scope

Golden query datasets, evaluation runners, retrieval-quality metrics, and evidence-backed promotion to chat defaults are deferred to PRD18. The PRD8 priority is to make the researcher-facing sandbox workflow complete enough to use and review before investing further in maintainer evaluation systems.
