---
name: git-github-publish
description: Safely initialize git, sweep for secrets before the first commit, publish a polished repo to GitHub with gh, and keep feature-branch commits reviewable. Use when the user wants to put a project under version control, make commits, create or push a feature branch, publish/open-source a repo, or push an existing local project to GitHub — especially when secrets, .env files, or personal data might be present.
---

# Git + GitHub Publish

Take a project from "no git" to "published" without ever committing a secret. The hard requirement: the **first commit must be clean** — there's no history to scrub when you init fresh, so the sweep happens before the commit.

## Workflow

1. **Init** on `main`:
   ```bash
   git init -q && git symbolic-ref HEAD refs/heads/main
   ```
2. **Confirm a real .gitignore exists** and excludes secrets and runtime junk: `.env`, `*.env` (but `!.env.example`), credential/recipient files, `.venv/`, `outputs/`, `logs/`, `cache/`. Add missing entries before staging.
3. **Stage, then verify sensitive paths are NOT tracked**:
   ```bash
   git add -A
   git ls-files --cached | grep -E '(^|/)\.env$|recipients\.yaml$|^outputs/|^logs/|\.venv/' || echo "clean"
   ```
4. **Content secret sweep** over staged files (catch hardcoded values, not just files):
   ```bash
   git grep -nI -iE 'sk-[A-Za-z0-9]{20}|api[_-]?key.{0,3}[=:].{8}|password.{0,3}[=:]|-----BEGIN|AKIA[0-9A-Z]{16}' --cached
   git grep -nI -iE '@gmail|<personal-name>' --cached    # personal emails / names
   ```
   Any hit → unstage, move the value to `.env`, add a `.example` template, re-sweep. Resolve every hit before committing.
5. **Public-repo polish** (skip for private):
   - `LICENSE` (MIT is a sensible default — confirm with the user).
   - README: install/usage/dev commands; a disclaimer if scraping third-party content (respect their ToS).
   - `.github/workflows/ci.yml` running lint + typecheck + tests.
6. **First commit** (confirm with the user first — committing/publishing is outward-facing):
   ```bash
   git commit -m "Initial commit: <one-line description>"
   ```
7. **Publish** (separate, explicit go-ahead — creating a public repo is hard to reverse):
   ```bash
   gh auth status                                   # confirm the right account
   gh repo create <name> --public --source=. --push
   gh repo view --web
   ```
8. **Confirm CI is green** on the first push.

## Ongoing feature-branch workflow

Use this for established repos after the first publish:

1. **Study the commit rhythm first**:
   ```bash
   git log --oneline --max-count=12 main
   ```
   Match the repository's existing scope. Prefer small, sequential commits over a mass commit. Split implementation, tests, docs, CI, and process updates when they are independently reviewable.
2. **Update relevant docs with behavior changes** before committing. Check the top-level README, module READMEs, tests docs, PRD status docs, and any command or API references near the edited code.
3. **Run the full quality gate, including formatting**. For this project style:
   ```bash
   uv run ruff format --check .
   uv run ruff check .
   uv run mypy src tests
   uv run pytest
   ```
   If the repo documents a different gate, run that complete gate rather than a subset.
4. **Keep CI/CD active on branch work**. Confirm workflows run for feature branches or pull requests, and update `.github/workflows/` in the same branch when local gates change.
5. **Commit incrementally** after each coherent slice passes its relevant checks. Prefer messages that describe the slice, for example `Add full-text search API`, `Document PRD4 search endpoints`, and `Typecheck tests in CI`.

## Safety rules

- Treat "make the first commit" and "create the public repo + push" as two separate confirmations. Public publishing is effectively irreversible (clones, caches, forks).
- A `.env.example` is good; a tracked `.env` is a leak. Same for `recipients.yaml` vs `recipients.example.yaml`.
- If history already exists and a secret was committed, rotating the secret is mandatory — removing it from history is not enough.
- Match the `gh` account to the intended owner before pushing; `gh auth status` first.
- Avoid rewriting pushed branch history unless the user explicitly asks for that rewrite.

## Related skills

- `project-scaffold` produces the `.gitignore` / `.env.example` this skill relies on.
- `pytest-pipeline-harness` provides the tests the CI workflow runs.
