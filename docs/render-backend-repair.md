# Render backend repair

Prepared on `fix/render-backend` from `dd363fd` (PR #20). No production schema,
configuration, release or catalog mutation was made. The existing
`c708communitymerge` migration is sufficient; shared models/migrations,
dependencies, Auth code and Gemini models/timeouts are unchanged.

## Read-only findings, 2026-10-11

Live HTTP: `/api/ready` 503; `/api/listings` and `/api/recommendations` 500;
`/api/health` and `/sign-in` 200. The locally configured Supabase Session pooler
is `aws-0-us-east-1.pooler.supabase.com:5432`, database `postgres`, user
`postgres.kkrvurwkufikbpzcbmek`, schema `public`. Its revision is
`c707browserroles`, without community tables/columns. The deployed-model query
produces `ProgrammingError`, SQLSTATE `42P01` (undefined table).
Counts: profiles 3, listings 2, requests 2; exchanges/messages/evidence/reviews 0.
Chrome DevTools inspection confirmed Render service `srv-db5iu4flk1mc73a5vvig`
serves `dd363fd77b54efa527a121a8206105fb211e0aad` from `main` and uses exactly
this database/project. Render logs contain repeated sanitized
`Unhandled API error (ProgrammingError)` messages. Its pre-deploy command is
empty, health check is `/api/health`, and automatic deploys are On Commit.
The deployed `APP_ENV` is `development`; `AUTH_MODE` and `STORAGE_BACKEND` are
both `supabase`. Gemini, Supabase and application secret keys are present.
The application secret meets the production minimum length and is not a known
development placeholder; no secret values were recorded. Production mode must
be enabled during the approved configuration release.

## 1. Confirm target, backup, approve migration

The existing Render service/database identity is confirmed above. Reconfirm its
live commit and target immediately before the approved migration.
Run the operator-only command in its environment using the reviewed build:

```bash
flask --app server.app backend-diagnostics
```

It reports `RENDER_GIT_COMMIT`, key presence (no secret values), database/storage
identity, current/expected revision, counts and sanitized SQLSTATE. Compare that
identity to Supabase and inspect sanitized Render errors. Confirm the public
and private Storage buckets retain server-only writes and private read gating.

A restricted read-only backup of the **locally configured project** is at
`var/render-backend/configured-supabase-before-c708.dump` (directory 0700,
file 0600). SHA-256:
`3b2fed883ad9a98d747685848540d96deda3f7fddcab230fc69d4a2e96182a95`.
The archive was restored into a separate local `render_backend_restore_test`
PostgreSQL database. All original backed-up fields survived the c707→c708
upgrade. Readiness, targeted import, catalog and recommendations passed there;
that disposable database was removed afterward. After confirming the Render
target, a fresh backup was taken at 2026-10-11 07:35:15 UTC:
`var/render-backend/confirmed-render-before-c708-20261011T073515Z.dump`.
SHA-256: `5ca5e9de6be89b8cf087946df3d3bf5a86f6ef44e7f0a5f754f3401af1282390`.
Its archive contents are readable. Target/count metadata and original-column
record hashes are in `var/render-backend/confirmed-render-backup.json` and
`confirmed-render-record-hashes.json`, with restricted local permissions.
Encrypt/export the backup through the operator's backup system and confirm the
hosted recovery point before upgrade. Postgres dumps exclude Auth and Storage objects.

After the actual target and its fresh recoverable backup are confirmed, request
approval for the single existing migration upgrade:

```bash
flask --app server.app db upgrade c708communitymerge
flask --app server.app backend-diagnostics --require-ready
```

Compare existing records across original columns, not just counts. Check browser
grants remain revoked and RLS is enabled on clubs/club_memberships. Recheck live
readiness, catalog and recommendations. Prefer forward repair; do not restore
over the shared database or downgrade to restore browser grants.

## 2. Approve code release and migration gate

Review/merge/deploy this branch only after approval. Docker packages the four
fixture banks, 52 licensed images, authoritative provenance and validators.
No new service, image source or runtime seed is added.

For the existing Render service, propose these settings:

| Setting | Proposed value |
| --- | --- |
| Pre-Deploy Command | `/bin/sh deploy/render-release.sh` |
| Health Check Path | `/api/ready` |
| APP_ENV | `production` |

The script applies the pinned reviewed `c708communitymerge` revision, then
requires readiness. Confirm it actually ran in deploy logs; the Procfile release
entry alone is insufficient. Update the pin only when reviewing future migrations.
If the service plan lacks predeploy, use one approved operator job before explicit
deployment; do not change plans silently or upgrade in every worker. Review the
service's automatic deployment behavior to retain the requested approval gates.
See Render's [predeploy documentation](https://render.com/docs/deploys#pre-deploy-command).

## 3. Review and approve the targeted import

The initial dry-run inventory is local, outside Git:
`var/render-backend/catalog-plan-before-upgrade.json`. It includes target
identity, stable IDs, exact insert values, prior-record hashes, proposed
actions, image SHA-256/size and licensed sources/credits. Plan SHA-256:
`66f25d4e3c260ca7b0fa068646516c846fd7a0c461ec8862f0468fc832d0950f`.
It proposes 12 visibly labeled non-login demo owners and 52 public demo listings.
`clothing-event-tablecloths` and `dorm-storage-bins-pair` are excluded. Existing
listings are preserved. No meeting spots, clubs/memberships, price references,
transactions, verification, ratings or impact records are created.

The initial inventory records c707 and cannot be applied after migration.
Generate and review a fresh inventory in the confirmed service environment:

```bash
flask --app server.app import-demo-catalog --dry-run > reviewed-catalog.json
# After reviewing this exact JSON and obtaining import approval:
flask --app server.app import-demo-catalog --apply --plan reviewed-catalog.json
```

Changed target, schema, assets or records reject the plan before upload. Apply
uses a PostgreSQL transaction advisory lock and existing-row locks. Every needed
image is saved to the public bucket and read back with its expected hash before
the transaction publishes any new listing. Save/readback/DB failures roll back
all rows and delete new objects. Failed cleanup reports generated public paths
in a sanitized log for operator retry. Storage already compensates for lost
upload responses.

Existing IDs, owners, descriptions, prices, status, timestamps, audience and
photos are preserved. Missing images can be filled on compatible public demo
rows already containing disclosure/credit; missing credit requires separate
description review. Drafts remain drafts, withdrawn rows remain withdrawn, and
active exchanges refuse photo repair. Real-owner/private-club collisions refuse
the job. Auth subjects are never remapped. A fresh repeat dry-run/apply uploads
nothing and preserves all rows. After a lost response, regenerate dry-run; the
old pre-import snapshot safely refuses rather than duplicating inventory.

## 4. Auth and Gemini live gates

Browser inspection confirmed the Site URL is currently `http://localhost:3000`
and the redirect allowlist is empty. The default email templates are active;
custom SMTP is not configured. The email-send quota is **2 per hour** and token
verification is **30 requests per 5 minutes per IP**. The app shows "Too many
sign-in requests" and has no saved session. A 403 `/verify` log explicitly says
`ONE-TIME TOKEN NOT FOUND`; its referer is `http://localhost:3000`. The 405 entry
used HEAD. These are distinct from the email quota; a 303 alone does not prove
successful verification. No additional magic links were requested.

Proposed Supabase URL corrections, pending approval:

| Setting | Required value |
| --- | --- |
| Site URL | `https://hack-nc.onrender.com` |
| Allowed redirect | `https://hack-nc.onrender.com/sign-in` |

Preserve other legitimately used callbacks. Existing Auth code constructs this
same-origin callback. Obtain approval for necessary dashboard changes, then
coordinate one fresh UNC magic link. Verify callback, `/api/me` UNC badge,
refresh, navigation and saved internal destination. A schema-related `/api/me`
failure alone is not proof that Auth failed. Do not use sandbox on production.

With that real session, call text and photo normalization once each. Require
`source: "gemini"` and useful structured fields grounded in the input; unknowns
remain unknown. Diagnose fallback through sanitized provider status/model/key
presence, never request text, tokens, keys or photo bytes. Keep existing manual
fallback/model order/timeouts unless evidence requires change. Sign out last
and confirm a protected request returns 401. Fresh login and production Gemini
remain unverified pending corrected URLs, email quota availability and a fresh
real session. Dashboard access now works through the user-provided Chrome
DevTools endpoint. Do not increase the email quota or add an SMTP service without
a separate team decision.

## Validation

Added regressions cover exact/read-only inventory, plan JSON roundtrip,
preservation/retry, save/readback/DB failure compensation, failed cleanup,
stale target/record refusal, real-owner/private-club collisions, photo-only
repair and strict asset validation. The isolated PG test begins at c707,
refuses premature/stale imports, verifies record preservation and browser
isolation, then checks readiness/catalog/recommendations after upgrade/import.

501 Python tests passed with `STORAGE_BACKEND=local` and the isolated local
`TEST_DATABASE_URL` (`campus_current_test`, unique schemas); this includes six
PostgreSQL checks. All 21 Node browser harness tests passed. Auth/API JavaScript
and release shell syntax checks passed. Provider tests are mocked; these results
do not establish live Auth/Gemini success. Docker built successfully as
`campus-current:render-backend`. It ran read-only as UID 10001 with network
disabled and a mounted isolated PostgreSQL socket. The release script migrated
the empty `render_image_test` database and passed diagnostics; Gunicorn returned
200 for readiness, catalog, recommendations and liveness, and anonymous `/api/me`
returned 401. All 52 packaged image hashes/provenance validated, and the
operator dry-run ran from the image. The container and dedicated image test
database were removed afterward. `git diff --check` and shell syntax passed.
Repeat all three live checks after the approved release/import.
