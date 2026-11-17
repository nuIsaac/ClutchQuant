# 12:12 implementation verification — November 17, 2026

Implemented on branch `rebrand/twelve-twelve`, based on remote main `f5e46bd`.

## Delivered

- 12:12 application/navigation/accessibility copy, browser/API titles, generated
  API identity, original favicon/apple icon and social preview artwork.
- Minimal dark theme requested during live review: near-black background,
  charcoal surfaces, gray borders, high-contrast text and restrained pale accent.
  Semantic tokens replace scattered palette values; decorative effects and
  colored/rotated team badges removed.
- Dashboard split into icons, initials, match cards and two dialog components.
  Old unused board/metric component and starter SVGs removed. Public wordmark SVG
  is an intentional export asset, also preserving the Docker public copy target.
- Same-origin watchlist migration with validation, quota handling, authoritative
  new key and rollback dual-write; four new regression tests.
- Renamed API/web image labels, disposable CI database/schema names, local
  container/project, backup unit templates, temporary caches and package identity.
- Existing database roles, storage identities and hosted-resource references
  isolated/documented; volume selection is explicit and cannot create an empty
  replacement. Applied schema migrations and immutable data remain untouched.
- Historical reports preserved in docs/legacy, deployment/design docs updated,
  and CI branding scan added with documented compatibility exceptions.

## Measured checks

| Check | Result |
|---|---|
| Backend pytest (API virtual environment, correct API working directory) | 183 passed, 26 skipped |
| Frontend Node test suite | 31 passed, including four watchlist tests |
| ESLint | Passed, zero warnings |
| Next type generation / TypeScript | Passed |
| Next production build after dark-theme/assets changes | Passed |
| Python compileall (app + migrations) | Passed |
| Deployment demo contract | Passed |
| Deployment/workflow YAML parsing | Passed |
| Shell syntax for deploy scripts | Passed |
| git diff --check | Passed |
| Branding scan | Passed; 107 documented compatibility/history lines retained before this report |
| Browser console | No error entries at final inspection |

Browser verification used the local frontend with the existing public hosted API,
not mock data. Observed 15 scheduled matches and 30,427 historical series. Verified
forecast detail and saved-forecast panels, search, saving a watchlist entry,
persistence after reload, removing the test entry, live-score navigation and an
honest no-live-matches state. Inspected desktop and narrow mobile layouts; no
horizontal overflow was measured in the narrow view. Reset the temporary viewport
and left the local development server and app tab open for further editing.

## Limits / remaining approval actions

Docker is not installed on PATH, so API/web Docker builds and the isolated full
container backup/restore smoke drill were not executed. No PostgreSQL test target
was configured; skipped integration tests are not claimed as passing. Python
compilation and unit tests are not substitutes for those deployment gates.

The user subsequently authorized committing and pushing this branch. Public deployment, GitHub rename, hosted resource rename, domain change,
credential rotation and live database operations remain outside this release. The current public
website therefore remains its prior deployment. The reviewed rollout instructions
are in rebrand-compatibility.md. The user's instruction requires explicit approval
before live infrastructure changes; the later user request explicitly authorizes this branch push.

Local preview: http://127.0.0.1:3000. API_URL is set only in the dev process to the
existing public API; no user environment file or deployed configuration was changed.

## Final UI refinement

Replaced the former sidebar/hero-card layout with compact top navigation, a
schedule summary strip, a default list view, unified search/tournament/date filters,
and a context rail. Grid view, watchlist, live feed, forecast details and model
notes remain available. Dialog styling is isolated in dialogs.css. Internal
market naming is now match-format.ts and forecast-primitives.tsx.

After the final layout change, filtering, grid/list selection, forecast dialogs and
methodology dialogs were rechecked through keyboard activation in the browser.
Frontend tests (31), zero-warning lint, typecheck and production build passed again.
