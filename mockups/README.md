# Workbench mockups

Static HTML/CSS mockups for the private scientific RAG workbench. These are historical review
artifacts and optional references now that the React app carries the implemented product UI.
They are not part of the default CI pipeline.

No build step and no backend. Open any file in a browser, or serve the folder.

## Screens

`index.html` links all nine: Repository Dashboard, Document Manager, Source Viewer, Search Lab,
Prompt Sandbox, Chat Workspace, Settings / Model Manager, Recreate Repository, Export Center.

Shared across every page:

- `styles.css` — design system (light/dark CSS variables, layout primitives). Light tokens are
  seeded from `../frontend/src/styles.css` so the eventual React UI inherits the same look.
- `app.js` — theme toggle (persisted, respects `prefers-color-scheme`), active nav, tabs,
  accordions, citation popovers, and modals. Pages still render without it.

## View locally

```bash
# either open mockups/index.html directly, or:
cd mockups
npm run serve      # http://127.0.0.1:4173
```

PowerShell:

```powershell
# either open mockups/index.html directly, or:
Set-Location mockups
npm run serve      # http://127.0.0.1:4173
Set-Location ..
```

Toggle light/dark from the control in the top-right of any page. Resize below ~900px to see the
sidebar collapse into a hamburger menu.

## Tests &amp; screenshots (Playwright, optional/manual)

```bash
cd mockups
npm install
npx playwright install --with-deps
npm test                 # smoke: every page loads, no console errors, theme toggle works
npm run screenshots      # writes screenshots/<desktop|mobile>/<page>-<light|dark>.png
```

PowerShell:

```powershell
Set-Location mockups
npm install
npx playwright install
npm test                 # smoke: every page loads, no console errors, theme toggle works
npm run screenshots      # writes screenshots/<desktop|mobile>/<page>-<light|dark>.png
Set-Location ..
```

The smoke test and the screenshot matrix (desktop + mobile x light + dark) can still be run for
manual design reference. `screenshots/`, `node_modules/`, `test-results/`, and
`playwright-report/` are gitignored.
