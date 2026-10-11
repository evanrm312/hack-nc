# Production follow-up — Evan

Branch `production-readiness`, based on merged PR #18 / main **2d9f014**.
PR #18 (`campus-completion`, a083d0a) and all other worktrees are preserved.
No merge, main commit, public deployment or teammate messages. Ratings/levels
and intelligence files are unchanged. All former Emily/Sid handoffs are Evan's.

## Completed

- Real deterministic homepage recommendations: bounded queries, availability /
  publication / ownership eligibility, current-user request compatibility and
  completed same-mode history, recency/diversity, explainable reasons and honest
  cold start. No Gemini, fake popularity or reputation rules. Previous buys remains
  completed purchases only. Exact weights in `docs/contracts.md`.
- Existing notifications completed: target accessibility, joined inbox, no
  feedback on reads, actual pause when hidden / stop on sign-out, and safe
  late-response handling. Existing committed-event/dedup hooks remain intact.
- Compact Aero About page at `/about`; returning marketplace stays `/`.
  Original photographs/font/sample images retained; names only, no invented bios.
- Dedicated rounded time rows fix overflowing controls; all date editors use
  Eastern time instead of mixing browser-local input and Eastern output. DST
  gaps/repeated hours are rejected. Compact dates omit seconds and repeated range
  text. Matches heading is smaller and aligned; helper copy shortened.
- Production Docker/Gunicorn, safe logs, DB readiness, shared DB quotas,
  PostgreSQL connection bounds, migration indexes, hourly systemd cleanup units,
  reverse proxy example, release/backup runbook and build/startup CI template.
- Confirmed security defect: Supabase tables had browser role grants with RLS
  disabled; anonymous REST messages collection returned 200. Forward migration
  revokes grants/default grants and enables server-only RLS. Anonymous now returns
  401 / SQLSTATE 42501. Both public/private bucket anonymous writes were denied.

## Verification in this run

Automated provider responses are mocked unless explicitly marked live. Python
checks use fresh isolated SQLite; PostgreSQL uses separately identified local
`campus_current_test` on 127.0.0.1:5544. DATABASE_URL is never a destructive target.

- Full Python: **463 passed, 0 failed, 0 skipped** (includes four isolated PG
  tests: fresh install, deployed-service-schema upgrade/preservation, concurrent
  publication + exchange notification dedup, competing reservation + repeated
  acceptance/messages). One existing Google SDK deprecation warning.
- Node browser harnesses: **20 passed, 0 failed, 0 skipped**. Auth/SDK/network/DOM
  are mocked. Date/DST formatting and visibility/sign-out polling have regressions.
- Firefox isolated journeys: **78 checks passed, 0 failed**: 41 page/desktop/
  mobile/auth/form checks, 14 two-sandbox-account service/notification/outsider
  checks, 8 draft failure/resume/retry/focus, 9 reduced-motion/closed-service/safety,
  6 date acknowledgement/lost-response retry. Not real Supabase accounts.
- Chrome DevTools MCP connected to user-launched Brave: inspected time controls,
  matches and About at 1440/1024/390 layouts; verified rendered recommendations
  exclude self, bounded response, clear purchase history and alerts on sign-out,
  and honestly switch to nonpersonalized browsing. Before mobile time controls
  overflowed; after controls fit at actual 390px. Keyboard and taskbar checks also
  ran in Firefox. Sale/borrow server lifecycles pass Python; item rooms were browsed.
- JS syntax, diff whitespace, Python Gunicorn config and Compose/CI YAML checks
  passed. Systemd verification reported absent docker.service/executable on this
  machine; unit installation/execution remains pending on the Docker host.

## Real providers and database

- Application SELECT 1 succeeded. Dev revision **b6c28d1f9a04 → c707browserroles**.
  Restricted public-schema backup saved before upgrade (path in deployment runbook).
  All 12 existing records preserved across original columns; no reseeding or reset.
  Current app DB readiness 200. Production database migrations have not run.
- Supabase Storage: genuine server-adapter public/private uploads, fresh-app byte
  retrieval, public anonymous retrieval, private anonymous denial and unauthorized
  adapter read denial passed. Both new test assets were deleted. Anonymous writes
  to both buckets denied. This is live Storage, **not** a real-user publication or
  exchange permission check; participant identities in the adapter check were
  isolated synthetic authorization context.
- Text and multipart photo normalization each returned **200 / source gemini**
  through actual Flask APIs. Server-side key, unchanged configured models; API
  identity sandbox, database/uploads isolated. No auth email requested.
- Native two-worker Gunicorn ran against development Supabase locally and returned
  ready. No debug server or public exposure. Docker build/startup is delegated to
  the prepared CI/host check because this machine lacks Docker.

## Blocked / release gates

The connected Brave profile has **no** Supabase session on the local live app;
`/api/me` returns 401. It was opened at `http://127.0.0.1:5062/sign-in` without
requesting an email. User reports an existing session elsewhere; no tokens or
magic links were copied. Thus confirmed UNC /me, real refresh/navigation/expiry/
sign-out, user-scoped provider publication/evidence and two-real-user notifications
remain pending. Alice/Billy dummy accounts are not substitutes for consenting
real participants. No repeated magic-link emails or impersonation.

Evan: complete real session checks (sign out last), obtain a second consenting
account, run Docker CI/startup, select machine/domain/TLS, configure Supabase
callback allowlist, review migrations/permissions and install the hourly timer.
Exact entrance/safety metadata remains unknown unless sourced; no guarantees.
Aarush: publish ratings/levels branch and agree on the additive contract in
`ratings-integration.md`, including service review applicability and reversal
points. Evan integrates when ready. No merge or deployment approval requested
until these concrete release gates are reviewable.

## Screenshots and previews

Main remains on 5055. Isolated feature preview: **http://127.0.0.1:5058**.
Local Supabase/Gunicorn verification app: **http://127.0.0.1:5062**.

Before/after: `/tmp/campus-production-qa/before/` and `after/`.
Matched time and results screenshots at 1440, 1024 and 390; About after screenshots
at all three sizes. Home/listing/account/requests/exchanges baseline/after shots
and all QA logs are in the same directory. Screenshots contain isolated QA records.
Current assets and licenses are unchanged; no generated artwork/new font.

Approval checklist: review feature diff + live permission change; pass Docker
build/startup; finish real auth/Storage/two-user checks; verify backups, domain /
callback / proxy / hourly timer; then explicit merge and public deployment approval.
