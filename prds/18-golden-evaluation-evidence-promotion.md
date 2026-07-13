# PRD 18: Golden Evaluation and Evidence-Backed Promotion

**Status:** Backlog.

## Problem Statement

PRD8 gives researchers a Prompt Sandbox for trying prompt versions, retrieval modes, rerankers, and local models without changing normal chat defaults. That is enough for hands-on exploration, but it does not yet give maintainers a repeatable way to prove that a prompt or retrieval configuration is better before making it the repository default.

From a maintainer's perspective, default changes should not depend on a few ad hoc sandbox runs. They need committed fixtures for deterministic checks, local golden query datasets for deeper review, retrieval metrics that explain wins and losses, and a promotion workflow that records which evidence justified a default change.

## Solution

Add a maintainer-focused evaluation layer on top of the Prompt Sandbox foundation. The system should support golden query datasets, run those queries across retrieval modes and reranker settings, compute relevance and latency metrics, preserve per-query evidence, and allow explicit promotion of a vetted prompt/retrieval/model configuration to repository chat defaults.

This PRD intentionally follows PRD8 rather than blocking it. The immediate product priority is a usable researcher-facing sandbox. This PRD owns the heavier maintainer tasks: repeatable relevance fixtures, metrics, evaluation summaries, and guarded promotion.

## User Stories

1. As a maintainer, I want a golden query dataset format, so that retrieval quality can be evaluated consistently over time.
2. As a maintainer, I want committed deterministic fixtures, so that CI can catch relevance regressions without requiring private local corpora.
3. As a maintainer, I want expected relevance labels to support expected terms first, so that fixtures can be practical before strict chunk labels are available.
4. As a maintainer, I want the dataset schema to allow future document IDs and chunk IDs, so that stricter relevance labeling can be added later without redesigning the format.
5. As a maintainer, I want validation errors for malformed golden datasets, so that fixture problems are easy to fix.
6. As a maintainer, I want to run golden queries across full-text, vector, hybrid, and reranked hybrid retrieval, so that retrieval modes can be compared directly.
7. As a maintainer, I want evaluation metrics such as recall@k, MRR, latency, and reranker win/loss, so that quality tradeoffs are visible.
8. As a maintainer, I want per-query evidence including retrieved IDs, ranks, score breakdowns, matched expected labels or terms, and latency, so that aggregate metrics can be audited.
9. As a researcher, I want evaluation summaries to preserve the tested prompt version, retrieval settings, reranker, model, dataset, and timestamp, so that I can understand what was measured.
10. As a researcher, I want model comparison to use the local model selected by the user during product runs, so that results reflect the system I am actually using.
11. As a maintainer, I want deterministic CI tests to validate model comparison through a mocked LLM boundary, so that tests do not depend on live local model availability.
12. As a maintainer, I want sandbox runs and evaluations to avoid changing chat defaults by themselves, so that experimentation remains safe.
13. As a maintainer, I want an explicit promotion button, so that a vetted prompt/retrieval/model configuration can become the chat default only by deliberate action.
14. As a maintainer, I want promotion to require visible evidence from a completed sandbox run, comparison, or golden evaluation, so that default changes are traceable.
15. As a maintainer, I want the promotion response to record the evidence artifact that justified the default change, so that later reviews can explain why defaults changed.
16. As a researcher, I want documentation for what evidence is expected before changing defaults, so that the workflow is clear.

## Implementation Decisions

- Build on PRD8 Prompt Sandbox data rather than replacing it. Evaluations may reference sandbox prompt versions, sandbox runs, sandbox comparisons, and repository chat defaults.
- Use a golden query schema that supports query text, expected terms, optional expected document IDs, optional expected chunk IDs, optional tags, and optional notes.
- Treat expected terms as the first committed fixture strategy. Document and chunk IDs are part of the schema for future stricter labels.
- Keep committed CI fixtures small and deterministic. They should use the existing test corpus and fake providers, not private local golden corpora.
- Add validation for missing query text, empty relevance labels, duplicate IDs, unsupported fields, and malformed optional labels.
- Run retrieval evaluations over full-text, vector, hybrid, and reranked hybrid. The evaluation runner should preserve both aggregate metrics and per-query evidence.
- Metrics should include recall@k, MRR, average latency, p50 latency, and reranker win/loss/tie against a selected baseline.
- Evaluation records should identify the dataset, prompt version, retrieval settings, reranker strategy, model, timestamp, aggregate metrics, and per-query results.
- Product generation, when answer text is needed for display, must use the selected local LLM. Mocked LLM generation is allowed only for tests.
- Add an explicit promotion workflow that can copy a selected sandbox prompt to the repository prompt library, make it active for chat, and apply selected retrieval/model defaults.
- Promotion must require a completed evidence artifact. A promotion request without evidence should fail with an actionable message.
- Sandbox runs, comparisons, and evaluations must never mutate repository chat defaults except through the explicit promotion endpoint/action.
- The UI should show enough evidence to compare a candidate configuration against the current default or selected baseline before promotion.
- Keep this PRD focused on maintainers and default-change governance; do not expand it into subjective LLM grading or broader experiment management.

## Testing Decisions

- Tests should assert external behavior: accepted/rejected datasets, computed metrics, persisted evaluation records, and default changes only through explicit promotion.
- Unit tests should cover golden dataset validation, recall@k, MRR, latency aggregation, and reranker win/loss/tie calculations.
- Integration tests should run the committed fixture through deterministic retrieval providers and verify persisted aggregate/per-query evidence.
- API tests should verify evaluation creation/reload and promotion guardrails.
- Tests should verify that sandbox runs, comparisons, and evaluations do not mutate repository chat defaults.
- Tests should verify that promotion mutates defaults only through the explicit promotion path and records the evidence artifact.
- Frontend contract tests should cover evaluation summary display, baseline/candidate evidence visibility, and the promotion action.
- Live local model checks should remain opt-in and documented. Default CI should use mocked LLM generation only at the LLM boundary.

## Out of Scope

- Building a general experiment tracking platform.
- Subjective LLM-as-judge answer grading.
- Fine-tuning prompts or models automatically from evaluation results.
- Replacing the PRD8 Prompt Sandbox comparison workflow.
- Bulk golden corpus management, labeling UIs, or private corpus synchronization.
- Chemistry-specific or patent-specific relevance label tooling beyond allowing tags and future document/chunk labels in the schema.
- Automatic default changes without maintainer approval.

## Further Notes

- This PRD splits the former PRD8 Phase 5, Phase 6, and Phase 8 scope into a future backlog item.
- PRD8 should still complete the researcher-facing Prompt Sandbox UI and final review before merging.
- The design should keep deterministic tests fast while leaving room for local, opt-in evaluations against real documents and local models.
