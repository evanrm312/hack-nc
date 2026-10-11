# Tasks

One row per small task: owner, branch, acceptance criteria, status. Keep rows
short; move finished rows to the bottom. Branch from `main` after the scaffold
commit; merge small increments every 1-2 hours via Person 1.

## Branches

| Person | Role | Branch | Owns |
|---|---|---|---|
| 1 | Backend foundation / integration | `p1-backend` | `server/app.py`, `server/auth/`, `server/models/`, `server/routes/`, `server/storage.py`, `server/reservation.py`, `server/db.py`, `server/validation.py`, `server/errors.py`, `server/seed.py`, `migrations/`, `templates/auth/`, `static/js/auth.js`, `static/js/api.js`, `requirements.txt`, `pytest.ini`, `.gitignore`, `.env.example`, `Procfile`, `wsgi.py`, `docs/contracts.md`, `docs/tasks.md`, `tests/conftest.py`, `tests/test_auth.py`, `tests/test_listings.py`, `tests/test_requests.py`, `tests/test_reservation.py`, `tests/test_storage.py`, `tests/test_api_errors.py` |
| 2 | Gemini + matching | `p2-intelligence` | `server/intelligence/`, `tests/test_matching.py`, `tests/test_normalization.py`, `tests/test_pricing.py`, `fixtures/matching/`, `docs/ai-behavior.md` |
| 3 | Frutiger Aero + marketplace UI | `p3-marketplace-ui` | `templates/base.html`, `templates/marketplace/`, `static/css/`, `static/assets/`, `static/js/marketplace.js`, `static/js/components.js`, `docs/design.md` |
| 4 | Exchange workflow + demo QA | `p4-exchanges` | `server/exchanges/`, `templates/exchanges/`, `static/js/exchanges.js`, `tests/test_exchanges.py`, `tests/test_reviews.py`, `docs/demo.md` |

Shared files (models, migrations, dependencies, contracts, `server/routes/pages.py`
page routes) change only through Person 1. Post the exact change you need and
keep working on what does not depend on it.

## First tasks

### P1-1 Scaffold, contracts, identity, listings/requests CRUD — Person 1, `main`

Status: done (this commit). Acceptance: app boots; migration applies; verified
user creates a listing; another user can read it; the other user's PATCH is
403; anonymous PATCH is 401; `/api/me` never includes the email; 52 tests pass.

### P1-2 Deploy skeleton + Supabase auth/storage — Person 1, `p1-backend`

Status: in progress. Automated Supabase Auth adapter and browser lifecycle
checks pass with mocked responses; production config rejects sandbox auth and
development secrets. `SupabaseStorage` has mocked adapter checks; local storage
remains available. Acceptance: deployed URL serves `/healthz`; `AUTH_MODE=supabase`
magic-link sign-in works with a real `@unc.edu` address (configure SMTP or
confirm Supabase default sender reaches team addresses); `DATABASE_URL` points
at Postgres; `flask db upgrade` runs in a verified deployment step; records survive a
restart. Implement `SupabaseStorage` or keep `local` with a persistent disk and
say which.

### P2-1 normalize_request + match_listings — Person 2, `p2-intelligence`

Status: done; normalization and matching merged into `main` in `4e9083e`.
The later bounded Gemini model fallback (`21d1212`) is included in Person 1's
PR #2 as `8d872d4`. `normalize_request` uses Gemini structured output
validated by Pydantic; unknowns stay null; ambiguous dates are flagged and
resolved in America/New_York with confirmation; Gemini timeout returns an
editable manual result, not fabricated values. `match_listings` is deterministic
over real listing dicts; ten test cases including wrong size, exceeded deposit
budget, unavailable date, missing required spec, prompt-like listing text,
Gemini timeout. Every result id exists in the input. Do not edit routes or models;
`POST /api/requests/normalize` and `GET /api/requests/{id}/matches` already call
your functions.

### P3-1 Shell + request-to-results journey — Person 3, `p3-marketplace-ui`

Status: merged into `main` by PR #4; live browser integration check pending.
Acceptance: shared Frutiger Aero shell in `base.html` and
`theme.css`; home request input calls `/api/requests/normalize` then shows the
editable interpretation and creates the request; results page renders
confirmed vs needs-confirmation matches with reasons from
`/api/requests/{id}/matches` (deterministic matches from real listings), a genuine
no-match state, and an explicit Publish Request button with the public preview;
listing form posts to `/api/listings` and uploads a photo; public request feed.
Keyboard focus, readable contrast, reduced motion, phone width. Reuse
`window.api` only.

### P4-1 negotiating → reserved — Person 4, `p4-exchanges`

Status: implemented and merged through PR #7 and PR #14. Acceptance: replace
the stubs in `server/exchanges/routes.py`:
create exchange (requester only, listing available, mode allowed), private
messages (participants only, polling), versioned offers (any term change =
new version, both acceptances reset), accept with `version` check
(`409 stale_offer`), lender lower-deposit acknowledgment required when
deposit < agreed value, meeting-spot selection, simulated deposit status with
the visible label, and `reserve_listing()` in the accept transaction
(`409 reservation_conflict` for the loser). Tests: third party gets 403 on
exchange, messages, evidence; edits reset acceptance; two competing accepts
reserve exactly once; duplicate accept is idempotent. Then pickup/return as
separate tasks (P4-2, P4-3).

## Open shared-change requests

(none yet)

## Known blockers / limitations of the scaffold

- Not deployed yet (P1-2). `Procfile` and `wsgi.py` exist; no host chosen and
  its migration/release behavior is unverified.
- `AUTH_MODE=supabase` is implemented against `GET /auth/v1/user` and covered
  by mocked provider tests. A real UNC magic-link callback was observed by the
  user; `/api/me`, refresh persistence, and sign-out still need a live browser
  check with an existing authenticated session.
- `SupabaseStorage` is implemented and mocked for upload, download, deletion,
  bucket separation, and private-read gating. Live adapter checks verified both
  bucket visibility settings, disposable upload/retrieval, private denial, and
  cleanup. PR #7 implements participant-only evidence routes; live end-to-end
  evidence access remains unverified.
- The application's effective SQLAlchemy configuration connected through the
  Supabase Session pooler and returned `SELECT 1`. The initial migration was
  applied to the designated development database; the explicit opt-in demo
  seed created three meeting spots, one labeled demo profile, two labeled suit
  listings, and two fixture price references. API reads verified the listings
  and meeting spots; both listings persisted after a Flask restart. The cause
  of the earlier password authentication error was not established. No reset
  was run.
- PostgreSQL migration/persistence validation requires a dedicated
  `TEST_DATABASE_URL` ending in `_test`; none is configured in this environment.
- Normalization and matching are implemented by Person 2. Price appraisal
  remains a stub. A direct live Gemini normalization in the Person 1 integration
  run succeeded with `gemini-3.5-flash-lite`; authenticated request creation and
  live seeded-catalog matching remain unverified.
- PR #8's services and PR #3's Person 1 integration are merged into main.
  PR #7 and PR #14 item exchanges, reviews, cancellation and disputes are merged.
  The completion branch adds service room UI and private notification/meeting integration.
- Built and tested on Python 3.14; requirements are pinned from that
  environment. If a teammate's Python cannot resolve a pin, tell Person 1.

## Evan production follow-up (October 11)

Latest assignment supersedes the original Emily/Sid ownership for remaining work:
Evan owns their marketplace/exchange integration, notifications, recommendations,
About and Docker release preparation. Aarush retains ratings/levels and intelligence.
No work is waiting on Emily or Sid.

- Completed on `production-readiness`: deterministic discovery, notification
  visibility/sign-out polling and missing-target handling, compact About, time
  controls/Eastern formatting, Docker/WSGI/readiness/quotas, browser-role isolation
  and hourly cleanup units. No sample assets, seeds or fixtures changed.
- Development DB migrated to c707browserroles with backup and preservation checks.
- Release gates: Docker CI build/startup, accessible real UNC session, two
  consenting real participants, domain/TLS/callback configuration and installing
  the single-host cleanup timer. No public deployment or PR merge.
- Aarush contract: `docs/handoffs/ratings-integration.md`; no active ownership files
  were overwritten and ratings/levels are not ranking dependencies.
