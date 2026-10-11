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
exchange/review tests exercise persisted state, participant authorization and
invalid transitions. Supabase auth/Storage provider checks are mocked unless
explicitly reported as live.

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
node --test tests/browser_*.test.cjs
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

`server/config.py` loads `.env` when the app starts; an already-exported shell
variable takes precedence. Restart Flask after editing `.env`. For the shared
Supabase Session pooler, use the URL copied from **Connect → Session pooler**,
change only the scheme to `postgresql+psycopg://`, and percent-encode reserved
password characters. If a read-only `SELECT 1` fails, compare the application's
effective driver, host, port, database, and username with a working PSQL command
without logging the password or full URL. An authentication error alone does not
identify whether the cause is a wrong secret, URL encoding, stale process
configuration, or another connection setting. Run migrations only after the
application connection succeeds.

Browser storage is scoped to the exact origin. Start the magic-link flow and
open its callback on the same scheme, hostname, and port (for example, use
`127.0.0.1:5055` throughout, not `localhost:5000` for one step). A saved
Supabase session can outlive a temporary `/api/me` database failure; the
header then reports that account details are unavailable without treating
the user as signed out. Confirm the actual `/api/me` status before concluding
that authentication failed.

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
check is: sign in, create a listing, publish its draft with a PNG through
`POST /api/listings/<id>/publish` as its owner, then request the returned
`public_photo_url` through Flask and compare the image bytes. Repeat the GET
after a server restart. The private bucket can be checked for direct anonymous
denial now; an end-to-end participant evidence check requires two consenting real
accounts and the implemented exchange evidence route. Private `SupabaseStorage.send` also requires
`authorize_private_read` in the current Flask request. If using local storage
on a persistent disk, keep `UPLOAD_DIR/private` outside directly served paths.

## Docker deployment preparation

Docker runtime, release migrations, readiness, quotas, server-only Supabase
permissions, backup/recovery and hourly cleanup are documented in
[docs/deployment.md](docs/deployment.md). `.env.production` must remain private.
The Docker image is never built with credentials. Do not deploy publicly until
Evan approves the release and the live verification gates pass.

```bash
docker compose build --pull
docker compose run --rm --no-deps -T web flask --app server.app db upgrade
docker compose up -d web
```

`/api/ready` verifies database connectivity and migration head; `/healthz` remains
process liveness. Supabase Auth site URL/callback allowlist must use the final
HTTPS origin. No web-worker scheduler or automatic seed runs.

## Targeted Render backend repair

The public app is `https://hack-nc.onrender.com`; Render settings were inspected,
and its schema and 52-record catalog import have been repaired. A real
login, refresh, sign-out and both live Gemini checks passed. Release settings,
backups and evidence are in
[docs/render-backend-repair.md](docs/render-backend-repair.md).

```bash
flask --app server.app backend-diagnostics
flask --app server.app import-demo-catalog --dry-run > reviewed-catalog.json
# Review the exact target/schema/assets/changes first:
flask --app server.app import-demo-catalog --apply --plan reviewed-catalog.json
```

Dry-run is the default and makes no database or Storage writes. The Docker
image packages the licensed assets and provenance; startup never imports them.
After merging this branch, use `/bin/sh deploy/render-release.sh` for predeploy.
Current main uses the equivalent pinned migration command without diagnostics.
Never run the broad `seed-demo` command on production or a shared database.
The user approved repair operations; merging into `main` still requires approval.

## Layout

```
server/            Flask app, config, db, models, auth, storage, reservation, routes
server/intelligence/  Person 2: normalize_request, match_listings, evaluate_price
server/exchanges/  Item and service exchange workflows
migrations/        Alembic migrations (Person 1)
templates/, static/  Jinja pages and browser code (base/marketplace: Person 3; exchanges: Person 4; auth: Person 1)
tests/             pytest
docs/              contracts, tasks, ai-behavior, design, demo
fixtures/matching/ Person 2 test fixtures
var/               local SQLite DB and uploads (ignored by git)
```
