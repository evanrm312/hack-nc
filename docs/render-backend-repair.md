# Render backend repair

Branch `fix/render-backend`, based on `dd363fd` (PR #20). The user approved all
repair operations on 2026-10-11; merging into `main` still requires approval.
No new models, migrations, dependencies, Auth logic, Gemini models or timeouts.

## Confirmed target and original failure

Render service `srv-db5iu4flk1mc73a5vvig` serves `https://hack-nc.onrender.com`
from `main`, commit `dd363fd77b54efa527a121a8206105fb211e0aad` before repair.
Dashboard environment and the operator connection independently matched:

- Supabase project `kkrvurwkufikbpzcbmek`.
- Session pooler `aws-0-us-east-1.pooler.supabase.com:5432`, database `postgres`,
  username `postgres.kkrvurwkufikbpzcbmek`, schema `public`.
- Revision `c707browserroles`; deployed community models required c708.
- Readiness 503, listings/recommendations 500; SQLSTATE `42P01` and sanitized
  Render `ProgrammingError` logs confirmed missing schema.
- Original profiles 3, listings 2, requests 2; no exchanges/messages/evidence/reviews.

## Production operations completed

The existing migrations upgraded this target to `c708communitymerge` once.
Original-column hashes matched every original record across 13 tables before
and after the targeted import. Club tables have RLS enabled; `anon` and
`authenticated` have zero public-table grants. Live readiness, listings and
recommendations returned 200 after upgrade.

The reviewed inventory inserted **52 public demo listings and 12 labeled,
non-login demo owners**. The two unlicensed-image entries
`clothing-event-tablecloths` and `dorm-storage-bins-pair` were excluded.
All 52 public HTTP photo bodies matched the licensed asset SHA-256 values.
The public catalog now contains 54 listings, including both original listings.
A fresh dry-run/apply preserved all 52 and inserted/uploaded nothing.
No clubs, memberships, meeting spots, price references, transactions or reviews
were seeded. Existing photos and private evidence authorization are unchanged.

Restricted operator artifacts live outside Git in `var/render-backend`:

| Artifact | Evidence |
| --- | --- |
| `confirmed-render-before-c708-20261011T073515Z.dump` | 47,856 bytes; readable custom public-schema archive |
| Backup SHA-256 | `5ca5e9de6be89b8cf087946df3d3bf5a86f6ef44e7f0a5f754f3401af1282390` |
| `confirmed-render-record-hashes.json` | Original columns and hashes, no raw private records |
| `catalog-plan-production-c708.json` | Exact target, IDs, values, provenance and asset hashes |
| Import plan SHA-256 | `09ca2111f2496fe68ab85dff06c4cb87682b858d3c514542785aa24ab001abc4` |
| `catalog-import-production-result.json` | inserted 52, photos filled 0, preserved 0 |
| `catalog-plan-production-after.json` | 12 owners and 52 listings preserved |

A preceding backup of the same target was restored into an isolated local
PostgreSQL database and upgraded/imported successfully; that disposable DB was
removed. Public-schema dumps exclude Supabase Auth and Storage objects.
Never restore over the shared database or downgrade to restore browser grants.

## Render release configuration

Saved in the existing service, without merging code:

| Setting | Value |
| --- | --- |
| Pre-Deploy Command | `flask --app server.app db upgrade c708communitymerge` |
| Health Check Path | `/api/ready` |
| APP_ENV | `production` |
| Auto-deploy | On Commit, `main` (unchanged) |

The direct migration command exists in current main. Saving it triggered
`dep-db5js57lk1mc73a8vvq0`. Saving production mode triggered
`dep-db5jstrbc2fs7395i58g`, which succeeded. Actual Render logs show the pinned
migration, "Pre-deploy complete!", and successful `/api/ready` checks.
The application secret meets production requirements; secret values were not
recorded or rotated. Auth/storage remain Supabase.

After this branch is approved for merge and available to Render, use
`/bin/sh deploy/render-release.sh` as the predeploy command. It pins the same
reviewed revision and additionally requires sanitized readiness diagnostics.
Confirm completion in actual Render logs. Update the pin only with reviewed
migrations. Docker packages the licensed assets, provenance and validators;
startup never seeds inventory. No plan upgrade or new service is needed.

## Targeted importer operation

```bash
flask --app server.app backend-diagnostics --require-ready
flask --app server.app import-demo-catalog --dry-run > reviewed-catalog.json
# Review the exact target, schema, IDs, assets and proposed changes first.
flask --app server.app import-demo-catalog --apply --plan reviewed-catalog.json
```

Dry-run is read-only and works before upgrade. Apply verifies the plan checksum,
recomputes the exact snapshot, requires c708, and uses a PostgreSQL advisory
transaction lock plus row locks. Every new public photo is uploaded and read
back with the expected hash before any new listing is published. Failures roll
back rows and delete newly uploaded objects; failed cleanup reports paths for
operator retry. A changed target, asset or record rejects the reviewed plan.

Existing IDs, owners, descriptions, prices, status, timestamps, audience and
photos are preserved. Photo-only repair requires compatible public demo rows
with existing disclosure/credit and no active exchange. Private-club and real
owner collisions fail. Auth subjects are never remapped. After a lost response,
regenerate the dry-run: a stale pre-import snapshot safely refuses duplication.
Never run broad `seed-demo` on production.

## Auth and Gemini verification

Supabase settings were corrected and their saved values verified:

| Setting | Saved value |
| --- | --- |
| Site URL | `https://hack-nc.onrender.com` |
| Redirect allowlist | `https://hack-nc.onrender.com/sign-in` |

Previously the site was localhost and the allowlist empty. A 403 `/verify` log
said `ONE-TIME TOKEN NOT FOUND`; the 405 entry used HEAD. A 303 alone did not
establish successful authentication. Email-send quota is 2/hour and verify
quota 30/5 minutes/IP. These limits, default templates and SMTP were unchanged.
One fresh sign-in email was successfully requested after correcting URLs;
the connected Chrome session returned `/api/me` successfully with
`verification_source: supabase`, `is_demo: false` and "UNC email verified".
The callback fragment was cleared. No tokens or inbox contents were collected.
The session survived page refresh and navigation to private exchanges.
`/sign-in?next=%2Fexchanges` returned to exchanges and cleared the saved
destination; external/protocol-relative destinations were rejected. Final UI
sign-out cleared the local token and `/api/me` returned 401 `auth_required`.

A live text normalization using that session returned `source: "gemini"`,
formalwear, borrow mode, a $20 budget as 2000 cents and $60 deposit limit as
6000 cents, with unspecified deadline remaining null. One live photo
normalization of the licensed suit reference also returned `source: "gemini"`,
formalwear, unknown mode, and `fixture: false`. Mocked tests alone do not establish production Gemini success. Preserve manual fallback and current model/timeouts
unless sanitized provider evidence requires a change. Sign out last.

## Validation

- 501 Python tests passed with local Storage and isolated PostgreSQL, including
  six PostgreSQL checks and c707→c708 preservation/privacy regressions.
- 21 Node browser tests passed; Auth/API JS and release shell syntax passed.
- Import regressions cover retry, stale plans, save/readback/database failures,
  cleanup failure reporting, real/private collisions and photo-only repair.
- Docker built `campus-current:render-backend`; read-only UID 10001, network
  disabled, isolated PG socket. Release migration/diagnostics passed; readiness,
  catalog/recommendations/liveness returned 200, anonymous `/api/me` 401.
- All 52 packaged asset hashes/provenance validated and image dry-run worked.
- `git diff --check` passed before production operations.

After the successful production deployment, live readiness, catalog and
recommendations all returned 200 again. Real Auth and Gemini checks above
passed; the final sign-out was verified. Remaining release step: obtain
approval to merge this branch into main, then use and verify the packaged
release script on Render. The currently active direct migration gate works.
