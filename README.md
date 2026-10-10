# Campus Current

Campus exchange for UNC: describe what you need, find a compatible item to buy
or borrow, agree terms, and coordinate a campus handoff. See `BUILD_BRIEF.md`
for the plan, `AGENTS.md` for team rules, `docs/contracts.md` for the API, and
`docs/tasks.md` for who is doing what.

Stack: Flask + SQLAlchemy + Flask-Migrate (Alembic), Jinja + vanilla JS,
pytest. SQLite locally, PostgreSQL (Supabase) when deployed. Gemini is called
only from Flask (Person 2).

## Setup

Built on Python 3.14; 3.11+ should work with the pinned requirements.

PowerShell (Windows):

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
Copy-Item .env.example .env
```

bash / macOS / Linux:

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
cp .env.example .env
```

`requirements-dev.txt` also installs the pinned project environment for test
work: `python -m pip install -r requirements-dev.txt`.

`.env` defaults to SQLite at `var/dev.sqlite3`, `AUTH_MODE=sandbox` with two
seeded identities (`alice@unc.edu`, `bob@unc.edu`), and local file uploads under
`var/uploads/`. It sets `APP_ENV=development` for the optional demo seed.
Nothing in `.env` is committed.

## Database

```bash
flask --app server.app db upgrade     # apply migrations (creates var/dev.sqlite3)
flask --app server.app seed-demo      # meeting spots + labeled demo inventory + fixture price ranges
```

`seed-demo` refuses nondevelopment mode and databases other than the local
`var/dev.sqlite3`, another explicitly named `*_dev` SQLite file, or a PostgreSQL
database ending in `_dev`. It is idempotent. Run migrations before seeding and
never seed a shared database.

For a **dedicated Supabase development project** whose database is named
`postgres`, use its Session pooler URL with the `postgresql+psycopg` driver
and the pooler's project-qualified username in `DATABASE_URL`. Percent-encode
reserved characters in the database password. After confirming
`APP_ENV=development` and that no teammates or users rely on the database, run:

```bash
flask --app server.app db upgrade
flask --app server.app seed-demo --allow-supabase-postgres-dev
```

The flag is required on each seed invocation, accepts only a Supabase session
pooler database named `postgres`, and is rejected in production. It inserts or
updates only labeled demo rows and does not delete other data.

To update an already-seeded **development** database, repeat the applicable
`seed-demo` command above (including the flag for Supabase `postgres`). It adds
the missing `type: "suit"` to both labeled suit rows
and availability bounds to the existing navy suit row in place. Their IDs,
other specifications, pickup notes, other listings, and user data remain intact.
An explicitly set type or date bound is left alone; review that listing if it was
customized. No database reset or new migration is needed for these JSON fields.

The seeded navy suit is available from `2026-10-12T12:00:00Z` through
`2026-10-16T22:00:00Z` (Monday 8 a.m. through Friday 6 p.m. in New York).
For the dated interview demo, confirm this editable request and submit it to
`POST /api/requests` as a different user from the demo lender. This is example
A, with an $80 maximum deposit:

```json
{
  "original_text": "Borrow a navy 40R suit for an interview Wednesday, October 14, 2026. Pickup Tuesday 2-4pm; return Thursday by 6pm. Rental budget $40.",
  "normalized": {"source": "manual", "category": "formalwear", "required_specifications": {"type": "suit", "jacket_size": "40R"}, "preferred_specifications": {"color": "navy"}},
  "modes": ["borrow"],
  "budget_cents": 4000,
  "max_deposit_cents": 8000,
  "needed_by": "2026-10-14T13:00:00Z",
  "use_start": "2026-10-13T18:00:00Z",
  "use_end": "2026-10-15T22:00:00Z",
  "pickup_windows": [{"start": "2026-10-13T18:00:00Z", "end": "2026-10-13T20:00:00Z"}],
  "area": "Central campus"
}
```

Example B submits the **same request body**, changing only
`"max_deposit_cents": 20000` ($200). The original text, normalized fields,
mode, rental budget, dates, pickup window, and area stay identical.

`GET /api/requests/{id}/matches` places the navy suit in
`needs_confirmation` for example A: type, size, rental budget, and dates fit,
while its proposed $200 deposit exceeds the $80 limit. It places the navy suit
in `confirmed` for example B, where the deposit fits. The charcoal 46L suit is
rejected in both. A lower deposit still requires negotiation and explicit lender
acknowledgment; matching does not change the owner's proposal.

After changing a model (Person 1 only):

```bash
flask --app server.app db migrate -m "describe change"
flask --app server.app db upgrade
```

## Run

```bash
flask --app server.app run --debug
```

Open http://127.0.0.1:5000/sign-in, pick a sandbox identity, and the header
shows the labeled profile. `GET /healthz` reports `{"ok": true, "auth_mode": "..."}`.
`GET /api/health` returns `{"status": "ok"}` for HTTP availability; neither
endpoint establishes database readiness.

Quick API check from a second terminal:

```bash
curl -H "Authorization: Bearer sandbox:alice@unc.edu" http://127.0.0.1:5000/api/me
curl http://127.0.0.1:5000/api/listings
```

## Test

```bash
pytest -q            # or: python -m pytest -q
```

`pytest.ini` puts the project root on the import path. Each test gets a fresh SQLite file, sandbox auth, and a temp upload folder
(`tests/conftest.py`). Person 1 tests cover auth, listings and ownership,
requests and sanitized views, reservation atomicity, storage validation, and
the error shape. Person 2's normalization and matching tests use mocked Gemini
responses and synthetic inventory; price appraisal and Person 4's
exchange/review tests remain stubs.

The migration and persistence tests apply the committed migration to a new
temporary SQLite file. PostgreSQL validation uses a separate database whose
name ends in `_test`; the test refuses the live `DATABASE_URL` and creates a
unique test schema. Set `TEST_DATABASE_URL` only to that isolated target:

```bash
export TEST_DATABASE_URL='postgresql+psycopg://test_user:PASSWORD@localhost:5432/campus_current_test'
python -m pytest -q tests/test_postgres_catalog.py
```

The PostgreSQL test skips when `TEST_DATABASE_URL` is unset. Never point it at
the application database. The URL must use the installed `postgresql+psycopg`
driver; the test creates and removes only a unique schema in the dedicated
`*_test` database. Do not use the live Supabase application database for tests.

Browser session checks (Node.js, no package install):

```bash
node tests/browser_auth.test.cjs
```

`POST /api/requests/normalize` returns a validated Gemini proposal when
`GEMINI_API_KEY` is configured, or an editable manual fallback with unknown
fields preserved as unknown. `GET /api/requests/{id}/matches` uses deterministic
checks against available catalog records and requires requester ownership.
The automated tests mock Gemini; a live call requires an explicit configured
development key and network access.

## Auth modes

- `AUTH_MODE=sandbox` (default locally): bearer token `sandbox:<email>` for an
  email in `SANDBOX_USERS`. No real verification; profiles are labeled
  "Sandbox identity (not verified)" and `is_demo=true`. Never use this on a
  public deployment.
- `AUTH_MODE=supabase`: the browser signs in with a Supabase magic link
  (`static/js/auth.js`); Flask verifies every request's access token against
  Supabase Auth and requires `email_confirmed_at` plus an exact `@unc.edu`
  domain. The client initializes on every page, updates the shared API token
  on refresh, and calls Supabase sign-out. Set `SUPABASE_URL` and
  `SUPABASE_ANON_KEY` (public) and
  `DATABASE_URL` to the Supabase Postgres URL. The service-role key stays
  backend-only.

## Supabase project setup and live checks

In the Supabase dashboard, enable email magic links and set the site URL to
the deployed origin. Add `https://YOUR_HOST/sign-in` to the allowed redirect
URLs. Configure email delivery if the default sender does not reach the team's
actual addresses. Copy the project URL and anon key into `SUPABASE_URL` and
`SUPABASE_ANON_KEY`; keep `SUPABASE_SERVICE_ROLE_KEY` server-side only. A live
auth check requires a real confirmed `@unc.edu` inbox: sign in at `/sign-in`,
follow the link, verify `/api/me` shows the UNC badge, refresh the page, then
sign out and confirm a protected request returns 401. Wrong-domain and
unconfirmed-email behavior is covered by mocked provider tests, not a live
Supabase project check yet.

For `STORAGE_BACKEND=supabase`, create two distinct buckets:
`SUPABASE_PUBLIC_BUCKET=public-listings` (public) and
`SUPABASE_PRIVATE_BUCKET=private-evidence` (private). Browser clients must not
have direct write access to either bucket or direct read access to private
evidence; only Flask uses the service-role key. A live public upload/retrieval
check is: sign in, create a listing, upload a PNG through
`POST /api/listings/<id>/photo` as its owner, then request the returned
`public_photo_url` through Flask and compare the image bytes. Repeat the GET
after a server restart. The private bucket can be checked for direct anonymous
denial now; an end-to-end participant evidence check waits for Person 4's
exchange evidence route. Private `SupabaseStorage.send` also requires
`authorize_private_read` in the current Flask request. If using local storage
on a persistent disk, keep `UPLOAD_DIR/private` outside directly served paths.

## Deploy (host pending)

No host has been selected. `Procfile` declares a release command, but whether
it runs depends on the chosen host; verify its release or predeploy feature
before relying on it. Configure these environment variables on the host:

| Variable | Value or purpose |
|---|---|
| `APP_ENV` | `production`; rejects sandbox auth and development secrets |
| `SECRET_KEY` | unique, nondevelopment random value |
| `DATABASE_URL` | deployed PostgreSQL URL using `postgresql+psycopg://` |
| `AUTH_MODE` | `supabase` |
| `ALLOWED_EMAIL_DOMAIN` | `unc.edu` |
| `SUPABASE_URL`, `SUPABASE_ANON_KEY` | project URL and browser-safe anon key |
| `AUTH_HTTP_TIMEOUT_SECONDS` | optional Auth provider timeout |
| `STORAGE_BACKEND` | `supabase`, or `local` only with a persistent disk |
| `SUPABASE_SERVICE_ROLE_KEY` | required for Supabase Storage; server only |
| `SUPABASE_PUBLIC_BUCKET`, `SUPABASE_PRIVATE_BUCKET` | distinct public/private bucket names |
| `UPLOAD_DIR` | required persistent path if using `local` storage |
| `MAX_UPLOAD_BYTES`, `STORAGE_HTTP_TIMEOUT_SECONDS` | optional upload size and storage timeout |
| `PORT` | supplied by the host for the web process |

`TEST_DATABASE_URL` is only for an isolated test target and must not point to
the deployed application database. `SANDBOX_USERS` is for local development.
`GEMINI_API_KEY` is optional for the Person 2 integration and is not needed by
the auth/storage scaffold. The host must supply `PORT` for the web command:

```bash
flask --app server.app db upgrade
gunicorn wsgi:app --bind 0.0.0.0:$PORT --workers 2
```

Run the migration as a deliberate deployment step before starting the new web
version. On the selected host, confirm how to run that first command once per
deploy; do not assume the Procfile `release:` entry is honored. Check
`/healthz`, the real magic-link flow, a public image upload/read, and listing
persistence after a restart. Deployment and these live checks remain pending.

## Layout

```
server/            Flask app, config, db, models, auth, storage, reservation, routes
server/intelligence/  Person 2: normalize_request, match_listings, evaluate_price
server/exchanges/  Person 4: exchange workflow (stubs now)
migrations/        Alembic migrations (Person 1)
templates/, static/  Jinja pages and browser code (base/marketplace: Person 3; exchanges: Person 4; auth: Person 1)
tests/             pytest
docs/              contracts, tasks, ai-behavior, design, demo
fixtures/matching/ Person 2 test fixtures
var/               local SQLite DB and uploads (ignored by git)
```
