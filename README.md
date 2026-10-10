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

`.env` defaults to SQLite at `var/dev.sqlite3`, `AUTH_MODE=sandbox` with two
seeded identities (`alice@unc.edu`, `bob@unc.edu`), and local file uploads under
`var/uploads/`. Nothing in `.env` is committed.

## Database

```bash
flask --app server.app db upgrade     # apply migrations (creates var/dev.sqlite3)
flask --app server.app seed-demo      # meeting spots + labeled demo inventory + fixture price ranges
```

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
the error shape. `tests/test_matching.py`, `test_normalization.py`,
`test_pricing.py` (Person 2) and `test_exchanges.py`, `test_reviews.py`
(Person 4) are empty stubs until those people fill them.

## Auth modes

- `AUTH_MODE=sandbox` (default locally): bearer token `sandbox:<email>` for an
  email in `SANDBOX_USERS`. No real verification; profiles are labeled
  "Sandbox identity (not verified)" and `is_demo=true`. Never use this on a
  public deployment.
- `AUTH_MODE=supabase`: the browser signs in with a Supabase magic link
  (`static/js/auth.js`); Flask verifies every request's access token against
  Supabase Auth and requires `email_confirmed_at` plus an exact `@unc.edu`
  domain. Set `SUPABASE_URL` and `SUPABASE_ANON_KEY` (public) and
  `DATABASE_URL` to the Supabase Postgres URL. The service-role key stays
  backend-only.

## Deploy (skeleton)

`Procfile` runs `flask db upgrade` on release and `gunicorn wsgi:app` for web.
Set `DATABASE_URL`, `SECRET_KEY`, `AUTH_MODE=supabase`, the Supabase keys, and
`GEMINI_API_KEY` as environment variables on the host. Not yet deployed; see
`docs/tasks.md` P1-2.

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
