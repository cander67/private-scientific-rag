# PRD 8: Prompt Sandbox and Evaluation

## Goal

Create a controlled space to compare prompts, search settings, rerankers, and models using repeatable golden queries.

## User Stories

- As a researcher, I can test prompts without changing normal chat defaults.
- As a researcher, I can compare the same query across retrieval modes and rerankers.
- As a maintainer, I can evaluate retrieval quality before changing defaults.

## Scope

- Prompt template/version model.
- Prompt Sandbox UI.
- Retrieved context preview.
- Side-by-side run comparison.
- Golden query dataset format.
- Evaluation runner.
- Retrieval metrics: recall@k, MRR, latency, reranker win/loss.

## Acceptance Criteria

- Same query can be run across full-text, vector, hybrid, and reranked hybrid.
- Prompt versions are saved and associated with runs.
- Golden evaluation can run with mocked LLM generation.
- Retrieval defaults are changed only after evaluation evidence.

## Test Plan

- Unit test prompt versioning.
- Unit test metric calculations.
- Integration test side-by-side run persistence.
- Golden query evaluation on the test corpus.

## Documentation References

- `tests/README.md` for test and golden corpus conventions.
- Elastic semantic relevance tuning: https://www.elastic.co/search-labs/blog/search-relevance-tuning-in-semantic-search
- Azure Search relevance overview: https://learn.microsoft.com/en-us/azure/search/search-relevance-overview
- SentenceTransformers evaluation documentation: https://sbert.net/docs/sentence_transformer/usage/evaluation.html
