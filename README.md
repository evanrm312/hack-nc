# Campus Current

M2 provides a public, read-only listing catalog backed by Flask-SQLAlchemy. `GET /api/health` checks HTTP availability only; it does not check the database. Catalog requests return a JSON 503 when no database is configured or reachable.

## Local setup

Run from the repository root with Python 3.14:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements-dev.txt
```

Verified M2 versions: Flask 3.1.3, Flask-SQLAlchemy 3.1.1, Flask-Migrate 4.1.0, SQLAlchemy 2.1.4, psycopg 3.3.6, and pytest 8.4.2.

Provision a **dedicated development PostgreSQL database** yourself, then set `DATABASE_URL` in your shell. `.env.example` shows the format and is not loaded automatically. Use a separate database for tests; never point `TEST_DATABASE_URL` at the application database.

```sh
export DATABASE_URL='postgresql+psycopg://app_user:replace-me@localhost:5432/campus_current_dev'
```

Replace the placeholders with the credentials for your development database. No Supabase, Gemini, or SMTP credentials are needed for M2.

## Apply the migration

After setting `DATABASE_URL`, run:

```sh
python -m flask --app server.app:create_app db upgrade
```

This applies the committed Profile and Listing migration. Run it deliberately when the schema changes; the app never migrates or creates tables on a request. Do not run it against a shared database without coordinating with the team.

## Optional demo seed

The seed command is explicit and idempotent. It runs only with `APP_ENV=development` and a database name ending in `_dev`. It inserts one fictional profile and one listing, each visibly labeled `DEMO`.

```sh
APP_ENV=development python -m flask --app server.app:create_app seed-demo
```

Run the migration first. Never use the seed command on a shared database.

## Run

```sh
python -m flask --app server.app:create_app run --debug
```

```sh
curl http://127.0.0.1:5000/api/health
curl http://127.0.0.1:5000/api/listings
```

The `--debug` server is for local development only. The catalog returns only active listings. See [docs/contracts.md](docs/contracts.md) for exact responses and pagination.

## Test

The default suite uses a new temporary SQLite database for each catalog test and applies the committed migration to it. It never uses `DATABASE_URL` for cleanup.

```sh
python -m pytest -q
```

For PostgreSQL integration, provision a separate database whose name ends in `_test`, set `TEST_DATABASE_URL`, then run:

```sh
export TEST_DATABASE_URL='postgresql+psycopg://test_user:replace-me@localhost:5432/campus_current_test'
python -m pytest -q tests/test_postgres_catalog.py
```

The PostgreSQL test refuses a target matching `DATABASE_URL` and uses a uniquely named test schema. It skips when `TEST_DATABASE_URL` is absent. SQLite results alone do not verify PostgreSQL migration behavior.
