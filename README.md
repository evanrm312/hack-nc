# Campus Current

A campus exchange for UNC students. Describe what you need in plain language,
see which real listings fit and why, agree terms privately with the other
student, and hand off in person at a public campus spot. Items can be bought or
borrowed; services such as tutoring can be booked. Payments and deposits are
simulated and labeled as such; no real money moves.

Live deployment: https://hack-nc.onrender.com (Supabase email and password
sign-in, UNC addresses only). Local development uses sandbox identities instead.

Project documents: `BUILD_BRIEF.md` (original plan), `AGENTS.md` (team rules),
`docs/contracts.md` (API shapes), `docs/tasks.md` (ownership),
`docs/design.md` (UI system), `docs/ai-behavior.md` (Gemini behavior),
`docs/demo.md` (exchange walkthrough), `docs/submission-draft.md` (Devpost draft).

## Features

- **Natural-language requests.** Gemini extracts mode (buy or borrow), category,
  required and preferred specifications, budget, deposit limit, dates, and
  area. Unknown fields stay unknown. The student reviews and edits every
  proposal before a request is saved. Ambiguous dates are shown as explicit
  Eastern-time dates that must be acknowledged.
- **Reference photos.** An optional photo yields broad visual attributes
  (category, type, color, pattern, style) that must be accepted or dismissed.
  A photo alone cannot create a request.
- **Deterministic matching.** Python checks mode, known required
  specifications, dates, budget, deposit affordability, and availability
  against real listings. Results are grouped into confirmed, needs
  confirmation, and rejected, each with reasons and shortcomings.
- **Public requests.** When nothing fits, the student previews the public
  fields and publishes. The feed hides precise schedules and contact details.
- **Item and service listings.** Sale, borrow, or both for items; eight service
  categories with price, duration, and availability windows. Listings are
  private drafts until the owner uploads a photo that the server decodes.
  Owners can replace photos and manage listings from My Listings.
- **Private exchanges.** Per-exchange messages (polling), versioned offers,
  acceptances that reset on any term change, explicit lender acknowledgment
  of a lower deposit, atomic reservation so an item cannot be double-booked,
  and a labeled simulated deposit status.
- **Pickup, loan, and return.** Private condition photos before handoff,
  mutual confirmation, loan tracking, before and after return photos, mutual
  return confirmation, cancellation before pickup, and a disputed state that
  never triggers a charge.
- **Services.** Scheduled sessions inside the provider's window, remote or
  in-person with a public meeting spot, and separate completion confirmations.
- **Reviews, notifications, profiles.** One structured review per participant
  on a completed exchange; a notification inbox; public profiles with avatar,
  bio, aggregate review and completion counts, and nothing private.
- **Clubs.** Seeded fictional clubs with join codes. Members can post club-only
  listings whose exchanges wait for a club manager's approval.
- **Home recommendations.** A bounded, explainable list based on the viewer's
  own open requests and completed history, with an honest cold start.
- **Frutiger Aero UI.** Shared components, keyboard-visible focus, readable
  contrast, reduced-motion support, desktop and 390 px phone layouts.

## Tech stack

| Layer | What is used |
|---|---|
| Server | Python 3.14, Flask 3.1, SQLAlchemy 2, Flask-Migrate (Alembic), Pydantic 2, Pillow, Gunicorn |
| Browser | Jinja templates, hand-written CSS, vanilla JavaScript with one shared API helper |
| AI | Gemini through the `google-genai` SDK, called only from Flask. Structured output with a JSON schema generated from Pydantic. Default model `gemini-3.5-flash-lite`, falling back to `gemini-3.5-flash` and `gemini-3.6-flash` only on 429 or 503, inside a 32-second budget. Image input for reference photos. Provider failure returns an editable manual form. |
| Data | SQLite locally; PostgreSQL on Supabase in production |
| Auth and files | Sandbox identities locally; Supabase Auth (email and password, confirmed `unc.edu` address) and Supabase Storage (public listing photos, private evidence bucket) in production |
| Deployment | Render web service with a pinned migration pre-deploy step and `/api/ready` health check; a Docker image is also defined [CONFIRM] which Render uses |
| Tests | pytest (522 cases) and Node's built-in test runner (27 cases) |

## Setup

Built and verified on Python 3.14.7 with the pinned `requirements.txt`. The
Windows commands below were run on October 11, 2026 (fresh virtualenv, install,
migrate, seed, run, tests); the bash block is the same steps and was not re-run.
Python 3.11+ should work with the same pins. [CONFIRM]

PowerShell (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

bash, macOS, Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

`.env` is ignored by git. Its defaults are SQLite at `var/dev.sqlite3`,
`AUTH_MODE=sandbox` with `alice@unc.edu` and `bob@unc.edu`, local uploads under
`var/uploads/`, and `APP_ENV=development`. To use the third demo account, edit
the line to `SANDBOX_USERS=alice@unc.edu,bob@unc.edu,carol@unc.edu`. Add a
`GEMINI_API_KEY` to try live extraction; without it the request form falls back
to manual entry.

## Database and demo data

```bash
flask --app server.app db upgrade      # apply migrations; creates var/dev.sqlite3
flask --app server.app seed-demo       # demo profiles, listings, meeting spots, clubs
```

Run the migration before seeding, and run `seed-demo` before signing in for the
first time so the demo display names are applied. `seed-demo` is idempotent: a
second run prints "nothing to do". It refuses production mode and any database
other than `var/dev.sqlite3`, a SQLite file whose name ends in `_dev`, or a
PostgreSQL database ending in `_dev`. A dedicated Supabase development project
whose database is named `postgres` needs the Session pooler URL with the
`postgresql+psycopg` driver, `APP_ENV=development`, and the
`--allow-supabase-postgres-dev` flag on every seed run; the flag is rejected in
production. Never seed a shared database.

What the seed creates on an empty development database:

| Rows | Count |
|---|---|
| Profiles | 13: 12 fictional catalog owners (two of them are the Alice and Bob sign-in identities) plus Carol |
| Listings | 59 (54 catalog listings, 21 of them services, plus 5 sign-in demo listings including one tutoring service); 52 carry licensed reference photos, 7 have none |
| Meeting spots | 3 |
| Clubs and memberships | 2 fictional clubs, 5 memberships |
| Price references | 2 labeled fixture ranges (not used by any rule yet) |

No exchanges, messages, reviews, or notifications are seeded.

**Windows note.** On Windows `seed-demo` currently fails with
`ValueError: Orphan/missing files` because
`fixtures/demo_catalog/validate_images.py` line 120 compares Windows path
strings against forward-slash manifest paths. Changing that line to
`path.relative_to(BASE).as_posix()` fixes it; this was verified locally and
then reverted because the file belongs to another teammate. The same issue
causes 24 test failures on Windows (see Tests). macOS and Linux are unaffected.

## Run

```bash
flask --app server.app run --debug
```

Open http://127.0.0.1:5000/sign-in and pick a sandbox identity. Verified
locally: `/`, `/sign-in`, `/about`, `/api/listings`, `/api/ready`, and
`/api/me` with a sandbox bearer token all return 200.

```bash
curl http://127.0.0.1:5000/healthz
curl http://127.0.0.1:5000/api/listings
curl -H "Authorization: Bearer sandbox:alice@unc.edu" http://127.0.0.1:5000/api/me
```

Restart Flask after editing `.env`.

## Tests

```bash
python -m pytest -q                       # Python suite
node --test tests/browser_*.test.cjs      # browser session, time zone, notification logic
```

Each pytest case gets a fresh SQLite file, sandbox auth, a temp upload folder,
and mocked Gemini. Six PostgreSQL tests skip unless `TEST_DATABASE_URL` points
at a dedicated database whose name ends in `_test`; never point it at the
application database.

Results on October 11, 2026 (Windows 11, Python 3.14.7):

| Run | Result |
|---|---|
| `python -m pytest -q` as committed | 492 passed, 24 failed, 6 skipped. All 24 failures are the Windows path issue above (`test_catalog`, `test_catalog_import`, `test_community`, `test_demo_catalog`, and the exchange preview test). |
| Same, with the one-line `as_posix()` change applied locally | 516 passed, 0 failed, 6 skipped |
| `node --test tests/browser_*.test.cjs` | 27 passed |

Pillow must be installed from `requirements.txt`; without it two test modules
fail to import and photo validation fails closed with 503.

## Demo accounts

Local sandbox sign-in has no password. Choose the identity on `/sign-in`, or
send the header `Authorization: Bearer sandbox:<email>`. Profiles are labeled
"Sandbox identity (not verified)" and `is_demo: true`.

| Email | After `seed-demo` | Suggested role |
|---|---|---|
| `alice@unc.edu` | Owns the clothing showcase listings (display name "Demo Wardrobe A (demo account)"), the navy 40R suit, a TI-84, and calculus tutoring (7 listings) | Lender or provider |
| `bob@unc.edu` | Owns the services showcase listings (display name "Demo Study A (demo account)") and a desk lamp for sale (8 listings) | Borrower, buyer, or second owner |
| `carol@unc.edu` | Owns the intentionally incompatible black 44L suit; manager of the Study Circle demo club. Must be added to `SANDBOX_USERS` first | Third party and club manager |

Of the 12 fictional catalog owners, two are mapped to Alice and Bob as shown
above; the other 10 ("Demo Tech A (demo account)" and similar) cannot sign in.
Fictional club join codes are listed in `docs/community-clubs.md`.

To walk through an exchange with two accounts, sign in as each one in a
separate browser profile or a private window; ordinary tabs share one identity.
`docs/demo.md` has the full pickup, return, dispute, and review sequence.

On the deployed app there are no sandbox accounts. Sign in with a real UNC
address and password; see `docs/team-test-scenario.md`.

## Deployment and operations

The production app runs on Render with Supabase for PostgreSQL, Auth, and
Storage. The repo carries both a `Procfile` and a `Dockerfile`; which one the
Render service uses was not checked for this README. [CONFIRM] Operational
details were kept in separate documents rather than here:

- `docs/deployment.md`: Docker build, release command, readiness, quotas,
  reverse proxy, hourly cleanup job, backup and recovery, migration chain.
- `docs/render-backend-repair.md`: the Render service configuration, the
  one-time schema repair, the reviewed 52-listing catalog import, and the live
  auth and Gemini checks that were recorded there. [CONFIRM] for the current
  state of the service.
- `docs/team-test-scenario.md`: the three-account acceptance test against the
  deployed app.
- `deploy/`: release script, nginx example, systemd units, CI workflow template.

Useful commands:

```bash
flask --app server.app backend-diagnostics             # read-only identity, counts, readiness
flask --app server.app import-demo-catalog --dry-run   # reviewed catalog import plan (never seed-demo in production)
flask --app server.app purge-exchange-locations        # hourly cleanup of expired private locations
docker compose build --pull && docker compose up -d web
```

`REQUIRE_EMAIL_CONFIRMATION=false` is a temporary team-testing mode: accounts
created without inbox confirmation are labeled "Test account (email not
verified)" and are blocked again when confirmation is re-enabled.

## Known limitations

- Payments and deposits are simulated. There is no payment provider,
  authorization expiry, or claims process. Disputes are flagged for manual
  review only.
- The price-range rule from the brief is not implemented. `evaluate_price`
  returns `insufficient_data`, item offers reject price references, and
  `tests/test_pricing.py` contains no tests.
- Reviews are stored and aggregated on public profiles, but there is no
  points or level system and no delayed mutual publication.
- Clubs are seeded fixtures. There is no club creation, roster, or role
  management.
- Service listings cannot store structured attributes such as a tutoring
  subject, so those requirements show as needs confirmation.
- `/listings/mine` has no dedicated page route; it is served through the
  listing-detail route and works, but should get its own route.
- Two catalog listings have no licensed reference photo.
- Gemini extraction is a proposal, not a verified fact. Everything it returns
  is editable, and the deterministic matcher does not guess size conversions or
  missing attributes.
- `seed-demo` and 24 tests fail on Windows until the one-line path fix above
  is applied.
- Meeting-spot safety attributes are recorded as unknown; the app makes no
  safety claims.
- Live Gemini and real UNC sign-in on the deployed app were verified by the
  deployment owner and recorded in `docs/render-backend-repair.md`; they were
  not re-run for this README. [CONFIRM]

## Team

Four UNC Chapel Hill students. Roles follow `docs/tasks.md`; commit authors
and branch names are consistent with them. Last names and the final split of
later work should be confirmed by the team. [CONFIRM]

| Person | Role | Main work |
|---|---|---|
| Evan (`evanrm312`) | Backend foundation and integration lead | Flask scaffold, models and migrations, sandbox and Supabase auth, storage, API contracts, service listings backend, draft publication, notifications, private meeting locations, recommendations, About page, Aero desktop shell polish, Docker, Render deployment and repair, password sign-in, most merges |
| Aarush (`adixit`) | Gemini and matching | Request normalization with structured output and model fallback, deterministic matching, reference-photo vision, service normalization and matching, the licensed demo catalog, community clubs and manager approval, public profiles |
| Emily (`Emily`, `Emily Zhu`) | Frutiger Aero and marketplace UI | Theme and shared components, home request flow, results, listing form and detail, public request feed, services UI, My Listings, listing photo upload and placeholders, exchange entry points, demo sign-in profiles in the seed |
| Sid (`Siddhant697`) | Exchange workflow and demo QA | Private negotiation and atomic reservation, condition photos, pickup and return, My Exchanges dashboard, reviews, cancellation, disputes, the exchange preview |

## AI coding assistants

We used Claude Code and Codex as coding assistants throughout the build, with
each teammate directing the work on their own module. The humans chose the
scope, reviewed the changes, and ran the checks described above. [CONFIRM] the
exact split between the two tools before publishing.

## Layout

```
server/               Flask app, config, db, models, auth, storage, reservation, routes, seed
server/intelligence/  normalize_request, match_listings, vision, evaluate_price (stub)
server/exchanges/     item and service exchange workflows, evidence, lifecycle
migrations/           Alembic migrations
templates/, static/   Jinja pages, CSS theme, browser JavaScript
tests/                pytest and Node tests
fixtures/             demo catalog (JSON, licensed images, validators) and matching fixtures
deploy/               release script, nginx example, systemd units, CI template
docs/                 contracts, tasks, design, ai-behavior, demo, deployment, handoffs
var/                  local SQLite database and uploads (ignored by git)
```
