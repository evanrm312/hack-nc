# Docker release runbook

No public deployment was made. Docker is the chosen packaging/runtime; Evan
still selects the machine, domain and TLS operator. The image uses the existing
Python 3.14 requirements, a nonroot user, Gunicorn (two workers × two threads),
and a read-only filesystem. No secrets, uploads, local databases or `.env` files
are copied into the build. The runtime control socket is disabled for read-only
containers. No automatic migrations, seeds or scheduler run in web workers.

## Configure and validate

1. Copy `deploy/production.env.example` to the ignored `.env.production`, or
   supply equivalent host secrets. Use a unique stable secret, the Supabase
   **Session pooler** URL with `postgresql+psycopg`, real browser anon key, and
   server-only Storage/Gemini keys. Never put secrets in build arguments.
2. Keep `APP_ENV=production`, `AUTH_MODE=supabase`, `STORAGE_BACKEND=supabase`.
   Buckets: public-listings public; private-evidence private. No browser upload
   or private-read policies. Flask's DB role must bypass RLS; browser roles have
   no application table grants. Do not seed production.
3. Set Supabase Auth site URL and exact `https://YOUR_DOMAIN/sign-in` callback
   allowlist. Preserve same-origin internal destinations. Confirm email delivery
   and exact confirmed `unc.edu` enforcement using a real session.
4. Build, back up the DB, review migrations, then run the release command once:

```bash
docker compose build --pull
docker compose run --rm --no-deps -T web flask --app server.app db upgrade
docker compose up -d web
curl --fail http://127.0.0.1:5055/api/ready
```

Default mapping is **loopback only**. Install a managed HTTPS reverse proxy;
`deploy/nginx.conf.example` shows the intended host-local topology. Replace its
domain/certificate paths. Set `TRUSTED_PROXY_HOPS=1` only when that single trusted
proxy overwrites forwarded headers and is the only path to the app. Direct local
preview uses 0. Gunicorn's `FORWARDED_ALLOW_IPS` must match the actual Docker
bridge peer address/subnet used by the isolated proxy; do not expose the backend
and then trust arbitrary forwarded headers. Test HTTPS recognition/HSTS and
client IP quotas before opening traffic. Flask does not trust forwarded Host.

Gunicorn deadline: 75 seconds; proxy read deadline: 80 seconds. Existing Gemini
32-second budget/model order and safe manual fallback are unchanged. Flask body
limit defaults to 5 MiB + 64 KiB; proxy limit is 6 MiB. Auth timeout is 5 seconds,
Storage 10 seconds. Each worker pool is bounded to four connections, no overflow,
10-second pool wait, 5-second connect deadline, 15-second SQL statement / 5-second lock deadlines, pre-ping and 300-second recycling. Include `sslmode=require` in the deployed DB URL.
Two workers can hold eight DB connections; leave capacity for release/cleanup jobs.

`/healthz` and `/api/health` establish liveness only. `/api/ready` runs SELECT 1
and checks the Alembic head, returning sanitized 503 on DB/schema failure.
Access logs omit query strings, headers and bodies; exception logs report type,
not SQL parameters. Do not enable debug, SQL echo or proxy query logging.

Production quotas: normalize 10/minute, other API writes 60/minute per resolved
identity (anonymous per IP). DB upserts share counters across workers. These are
fixed windows, not global provider-spend caps; monitor usage and tune through
environment variables. Failure to access quota storage fails writes closed (503).

## Hourly retention job

Install `deploy/campus-location-cleanup.service` and `.timer` on the **single
Docker host** at `/etc/systemd/system`, with app files at `/opt/campus-current`.
The service uses Compose's environment secrets and the same reviewed image.
Enable the timer after deployment approval:

```bash
sudo systemctl daemon-reload
sudo systemctl enable --now campus-location-cleanup.timer
systemctl list-timers campus-location-cleanup.timer
journalctl -u campus-location-cleanup.service
```

The unit runs `flask --app server.app purge-exchange-locations` hourly, with a
small randomized delay and a catch-up run after downtime. Systemd does not start
another instance while the unit is active. SQL deletion is safe under overlapping
external invocations: only expired participant contexts (24-hour retention) and
quota counters older than one hour are deleted. Public agreed meeting spots,
profile preferences, offers and exchange records are retained. Terminal exchange
transitions also remove temporary locations. Counts are logged without locations.
A DB error rolls back, logs a sanitized error and exits nonzero; monitor failures
and retry manually. No scheduler inside Gunicorn. The timer is prepared, not installed.

## Migrations and access isolation

Chain: a44534641a4c → b6c28d1f9a04 → c701publication → c702notifications →
c703locations → c704creationkeys → c705exchangekeys → c706runtime →
c707browserroles (single head). c706 adds discovery/inbox/expiry indexes and
shared quota counters. c707 revokes browser/PUBLIC table grants, enables RLS,
and removes default browser table grants for the migration role in this schema.
It preserves postgres/service-role server access. No Storage policy is changed.
Future Aarush tables need the same server-only permissions; review them explicitly.

**Development:** upgraded from b6c28d1f9a04 to c707browserroles in this run.
The public schema backup is private on the local machine at
`/tmp/campus-production-qa/development-before-upgrade-20261011-014814.dump`.
All twelve preexisting application records were compared across their original
columns and preserved. Anonymous REST table access changed from HTTP 200 to 401;
remaining browser table grants are zero. Live app readiness passed.
**Production:** not applied; there is no selected public environment yet.
**Isolated PostgreSQL:** fresh install and upgrade from service schema passed,
including browser role grant revocation, record preservation and concurrent
publication/reservation/accept/message checks. Never substitute DATABASE_URL for
TEST_DATABASE_URL. Test targets must be distinct dedicated `*_test` databases.

## Backup and recovery

Before release, obtain a verified Supabase snapshot/PITR restore point and a
restricted application-schema `pg_dump --format=custom --schema=public --no-owner`
backup, supplying passwords through secure environment settings. Store backups
encrypted with access/retention controls. Storage bytes need a separate bucket
backup/inventory; Postgres backup alone does not include objects or Auth recovery.
Validate a restore on a separate project/database before relying on recovery.

Prefer forward repair. c707 downgrade deliberately does **not** restore unsafe
browser grants; other downgrades may delete new data. If recovery is necessary,
stop writes, restore into an isolated replacement, verify records/permissions and
Storage references, then coordinate a deliberate cutover. Use `pg_restore --no-acl`
and reapply reviewed permissions; an older dump can contain unsafe browser grants.
Do not restore over the shared database as a test. This run created the dev backup;
it did not perform a live backup restoration or enable PITR.

## Verification gates

`deploy/verify.workflow.example.yml` is a prepared GitHub Actions workflow for Python + browser harnesses + isolated PG and
building/starting a read-only Docker image with placeholder provider config. It never
publishes an image or deploys. A temporary rootless Docker daemon built the image
and started it read-only as UID 10001 with two Gunicorn workers. Fresh migrations,
readiness, unauthorized /me, the About page and repeated cleanup passed against
isolated PostgreSQL (mounted Unix socket, placeholder provider credentials).
Native Gunicorn readiness also passed against development Supabase. Compose,
TLS/proxy and the hourly systemd timer still need checking on Evan's selected host.
Real UNC session and two-real-participant journeys remain separate live gates;
sandbox and adapter checks do not establish them.

Sources inspected: [Docker build guidance](https://docs.docker.com/build/building/best-practices/),
[Gunicorn settings](https://gunicorn.org/reference/settings/),
[Supabase Session pooler](https://supabase.com/docs/guides/database/connecting-to-postgres),
[RLS](https://supabase.com/docs/guides/database/postgres/row-level-security),
[Storage policies](https://supabase.com/docs/guides/storage/security/access-control).

GitHub rejected a workflow-file push because the existing OAuth credential lacks
`workflow` scope, and SSH authentication is unavailable. The full workflow is
preserved as a deployment template instead. Evan can copy it to
`.github/workflows/verify.yml` with a credential authorized for workflows; no
credential permissions were changed automatically.
