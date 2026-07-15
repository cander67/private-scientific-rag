# PRD 20: Repository Dashboard and Home Alias

**Status:** Complete and closed.

## Problem Statement

The app shell currently shows Home and Repository Dashboard navigation items, but neither is implemented as a navigable product surface. Users who start the app need a clear first screen that explains the current repository state, highlights what is ready or stale, and gives direct routes to the most common workflows.

Without a dashboard, repository health is spread across Document Manager, Search Lab, Chat Workspace, Export Center, and Recreate Repository. That makes it harder to know whether a repository is ready for search/chat, whether indexes are current, which local models are available, or what should be done next after import, recreate, or a clean install.

## Solution

Build a Repository Dashboard as the app's default home surface. The dashboard should summarize the active repository, key corpus counts, index health, model readiness, active configuration, recent activity, and common actions. The `#home` route should alias to the dashboard so Home and Repository Dashboard lead to the same implemented view.

The dashboard should be a status and navigation surface, not a replacement for detailed workflow pages. It should link users into Document Manager, Source Viewer, Search Lab, Chat Workspace, Prompt Sandbox, Export Center, Recreate Repository, and Settings / Models where deeper work happens.

## User Stories

1. As a researcher, I want Home to open a useful repository overview, so that the app does not start on an empty or dead route.
2. As a researcher, I want Repository Dashboard to show the active repository name, so that I know which repository I am looking at.
3. As a researcher, I want to switch repositories from the dashboard, so that dashboard status updates for the selected repository.
4. As a researcher, I want to see document, chunk, chat, retrieval, and sandbox counts, so that I can quickly understand repository scale.
5. As a researcher, I want to see full-text index status, so that I know whether sparse search is ready.
6. As a researcher, I want to see vector index status, so that I know whether semantic and hybrid search are ready.
7. As a researcher, I want to see stale or partial index warnings, so that I know when a rebuild is needed.
8. As a researcher, I want to see Qdrant availability, so that vector rebuild and search failures are explainable before I start.
9. As a researcher, I want to see local model readiness for chat, embedding, and reranking models, so that missing setup is visible.
10. As a researcher, I want to see the active repository configuration summary, so that I know the current chunking, embedding, reranking, and chat defaults.
11. As a researcher, I want direct actions for upload, search, chat, prompt sandbox, export, and recreate, so that I can move from status to work quickly.
12. As a researcher, I want a clear empty state when no repository exists, so that I can create a default repository or recreate from an export bundle.
13. As a researcher, I want a recreated repository to show useful dashboard status after restore, so that transfer success is visible in one place.
14. As a researcher, I want recent activity to show recent documents, retrieval runs, chats, exports, and recreate events where available, so that I can resume work.
15. As a researcher, I want dashboard warnings to link to the page that can fix the issue, so that stale indexes or missing models are actionable.
16. As a maintainer, I want dashboard data served by stable summary APIs, so that the UI does not duplicate count and readiness logic from several pages.
17. As a maintainer, I want Home and Repository Dashboard routes to resolve consistently, so that deep links and sidebar navigation are predictable.
18. As a Windows user, I want dashboard setup warnings to use Windows-friendly wording where relevant, so that local model and service guidance is not Bash-only.

## Implementation Decisions

- Add `home` and `dashboard` view routing to the frontend. `#home`, an empty hash, and `#repository-dashboard` should resolve to the same Repository Dashboard view.
- Replace the disabled Home and Repository Dashboard sidebar entries with navigable links.
- Keep the dashboard read-mostly. Mutating actions should navigate to the workflow surface that already owns the operation unless the action is a small, well-established command such as triggering an existing index rebuild.
- Add or extend repository summary APIs to provide counts, index status, model readiness summaries, active settings summary, and recent activity without requiring the frontend to call every existing endpoint independently.
- Reuse existing readiness and index status logic where possible so dashboard values match Search Lab and Chat Workspace.
- Reuse the existing repository selector behavior so switching repositories updates the dashboard and the rest of the app consistently.
- Use the existing repository-dashboard mockup as visual guidance, but adapt it to the current React/Vite app conventions and shipped design system.
- Dashboard quick actions should link to existing implemented routes. Home should not introduce a separate standalone landing page.
- Empty state should offer create/use default repository and recreate-from-bundle actions. Broader delete/reset actions belong to repository administration reset scope.
- The dashboard should not become a settings editor. It may show settings summaries and link to Settings / Models.

## Testing Decisions

- Tests should assert external behavior: Home and Repository Dashboard navigation, displayed repository summary, warning states, and action links.
- Frontend contract tests should verify `#home` and `#repository-dashboard` route to the dashboard view.
- Frontend contract tests should verify disabled placeholder links are replaced with navigable links.
- Integration tests should verify repository summary responses for empty repositories, populated repositories, stale indexes, partial indexes, and unavailable vector services.
- Tests should verify dashboard counts match persisted repository records and do not include other repositories.
- Tests should verify recreated repositories appear correctly in dashboard summaries after PRD9 restore.
- Tests should verify dashboard warnings are informational and do not mutate repository state by themselves.
- Live checks for Qdrant or local models should remain opt-in; default CI should use deterministic fakes or mocked readiness boundaries.

## Out of Scope

- Full repository deletion or reset workflows.
- Editing settings or model defaults directly from dashboard controls.
- Building a general analytics or audit timeline system.
- Long-running background job orchestration.
- Subjective quality scoring or golden evaluation summaries.
- Replacing existing Document Manager, Search Lab, Chat Workspace, Prompt Sandbox, Export Center, or Recreate Repository pages.

## Further Notes

- This PRD closes the current navigation gap for `#home` and `#repository-dashboard`.
- The dashboard should help users understand what is ready now, what needs attention, and where to go next without prescribing a specific future PRD order.
- Repository administration and destructive reset actions remain covered by the repository administration/reset backlog item.
