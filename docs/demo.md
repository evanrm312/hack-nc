# Person 4 workflow and review handoff

Private uploads, pickup, and return extend the existing negotiation/reservation
flow on `p4-exchanges`. The My exchanges dashboard now includes persisted
progress, private photo previews, and completed-exchange reviews. Cancellation
before pickup and the standalone `/dispute` endpoint are also implemented;
contested returns support both `/dispute` and `/return` with `action: issue`.

## Current preview and validation (2026-10-11)

The running Person 4 preview uses **port 5050** and persistent data in
`var/exchange-preview`. The previous port 5000 server was stopped. Open
`http://127.0.0.1:5050/sign-in` (or forwarded Codespaces port 5050), choose Bob,
then click **My exchanges**. Alice can respond in a separate browser profile or
private window; ordinary tabs share an identity. Sign in again on the new port.
The original `var/dev.sqlite3` database is preserved. Preview inventory and
identities are visibly labeled sandbox examples; startup does not fabricate
exchange records, reviews, payments, or deposits. Existing preview exchanges
remain saved across restarts.

Bob selects an available item owned by another member and its supported Buy or
Borrow mode, then starts the private exchange. The browser rehearsal verified
inserting a listing and its public photo through the existing listing API,
followed by selecting it and starting an exchange. The shared **New listing**
page remains a Person 3 placeholder and is outside this Person 4 task.

After the shared API-error test update and cancellation/dispute implementation,
`.venv/bin/python -m pytest -q` reported **181 passed**, with four existing
Flask-SQLAlchemy/Alembic deprecation warnings. JavaScript syntax, Python
compilation, and Git whitespace checks passed.

Chromium verified the actual **My exchanges** navigation and sign-in on live
port 5050 without creating test transactions there. A separate temporary
SQLite preview exercised loading/error recovery, a genuine empty account,
listing insertion and photo bytes, item selection, private message polling,
offer edits that clear acceptances, stale-offer rejection, explicit lender
collateral acknowledgment, sale pickup, private photos, completed reviews and
review-error recovery, a full loan return, contested return, cancellation
before agreement and after reservation, participant permissions, keyboard
focus, photo retry, identity switching, and sign-out. The desktop and 390px
screenshots were visually inspected; no phone overflow or JavaScript page
errors were observed. Artifacts are in
`/tmp/campus-current-dashboard-artifacts/`. Browser tooling used its temporary
path; image validation used Pillow 12.3.0 from the normal project venv.

Browser command used:

```bash
PYTHONPATH=/tmp/campus-current-browser PLAYWRIGHT_BROWSERS_PATH=/tmp/campus-current-browsers .venv/bin/python /tmp/campus-current-exchange-dashboard-browser.py
```

## My exchanges dashboard

`GET /exchanges` renders the existing Person 4 template and `exchanges.js`
inside the shared Campus Current shell. The dashboard authenticates through
`window.api`, reads only the current participant's saved exchanges, and shows
loading, retryable API errors, sign-in guidance, and a genuine empty state.
It does not create or substitute example exchange records.

`GET /api/exchanges` retains `exchanges: []` for an empty account. Each actual
exchange now includes its listing summary, latest `current_offer`, public
participant profiles, `pickup_meeting_spot`, `return_meeting_spot`, evidence
metadata, evidence-backed `confirmations`, simulated `deposit_status`,
`my_review`, and `can_review`. Related records are fetched in batches scoped
to those exchange IDs. Photos retain their participant-only API URLs; image
previews load only when the photo disclosure opens. The endpoint has
`Cache-Control: private, no-store`. It does not include private messages or
another participant's review.

Cards show the saved Eastern meeting times and locations, separate fee/value/
deposit amounts, condition/accessories, pickup and return confirmations, active
loan progress, disputed-return reason, and saved review. Missing terms remain
unknown. Buttons lead to the existing room's photo uploads, explicit pickup
confirmation, return initiation/confirmation, and contested-return forms.
Completed exchanges expose optional structured review forms on the dashboard.

`POST /api/exchanges/{id}/review` now persists the existing `Review` model:
the server derives reviewer/reviewee from authenticated participation, requires
`completed`, validates integer stars 1–5 plus all five structured answers
(`yes`, `no`, `not_applicable`), and requires `returned_on_time: not_applicable`
for sales. Comment is optional, at most 2,000 characters. A per-exchange write
lock and existing unique constraint prevent duplicate/concurrent submissions.
Errors use `exchange_not_completed` or `already_reviewed` (409), and the shared
400 validation shape. Submission and refresh failures preserve useful errors;
review drafts remain available after a failed submission. Reviews are stored
immediately and cannot be edited. Public review aggregation/publication is
outside this dashboard change.

No shared models, migrations, dependencies, auth helpers, page routes, theme,
or contracts were edited by Person 4. `Pillow==12.3.0` has now been added to
the shared requirements by the user. Person 1 should add these response fields/
review semantics to `docs/contracts.md`. The obsolete fixture/stub assertion in
`tests/test_api_errors.py` has been updated at the user's request.

Dashboard files changed: `templates/exchanges/my_exchanges.html`,
`templates/exchanges/room.html`, `templates/exchanges/_styles.html`, `static/js/exchanges.js`,
`server/exchanges/routes.py`, `server/exchanges/lifecycle.py`,
`tests/test_exchanges.py`, `tests/test_reviews.py`, and `docs/demo.md`.

Initial dashboard validation (2026-10-11): the relevant exchange/review/auth/storage/
reservation suite reported **128 passed**. The full Python suite reported **156 passed,
1 failed**. The sole failure is Person 1's already documented obsolete
`test_exchange_stubs_are_labeled_fixtures_and_writes_501`; all dashboard,
review, privacy, concurrency, and lifecycle tests passed. JavaScript syntax
and whitespace checks passed. Chromium verified the running `/exchanges` on
port 5000 read-only, then exercised actual APIs on an isolated SQLite database
for loading/error recovery, empty accounts, sale pickup, private preview and
retry, completed reviews and review-error recovery, full loan return, contested
return, third-party/anonymous evidence denial, and desktop/390px layout.
No JavaScript page errors or phone overflow were observed. Screenshots were
captured in `/tmp/campus-current-dashboard-artifacts/` and visually inspected.
The test transactions were created only in a temporary isolated preview
database, never in the running port 5000 database. Port 5000 was restarted
with the current backend and the temporary Pillow installation.

After the Pillow pin was added, the normal `requirements.txt` install succeeded
and Pillow 12.3.0 loaded from `.venv/lib/python3.14/site-packages/PIL`, with
JPEG and WebP decoding available. Running the relevant suite with
`env -u PYTHONPATH .venv/bin/python -m pytest -q tests/test_exchanges.py tests/test_reviews.py tests/test_reservation.py tests/test_storage.py tests/test_auth.py`
reported **128 passed**. The Chromium journey above was rerun successfully
using Pillow from the venv; only browser tooling used a temporary path. Port
5000 was restarted against the same local database without the temporary
Pillow path, and `/exchanges` was verified in the browser. The dependency
blocker is resolved. The shared fixture/stub test is also resolved; see the
current validation under Teammate dependencies below.

## Implemented behavior

- Existing versioned offers, acceptance reset, explicit lender acknowledgment,
  atomic reservation, and simulated payment/deposit disclosure remain intact.
- Evidence uses the provided private storage helper. Existing records persist
  exchange, uploader, purpose (`stage`), MIME type, and UTC creation timestamp.
  Filenames and client MIME types are not trusted.
- Uploads must decode completely as still JPEG/PNG/WebP photos, at most
  `MAX_UPLOAD_BYTES` (normally 5 MiB) and 16 megapixels. Invalid content, missing
  files, excessive size, unauthorized uploaders, and inappropriate stages fail
  before saving evidence. A DB failure removes the newly stored file.
- Metadata, original bytes, and previews are participant-only. No public photo
  URL or private storage path is exposed. Responses use private/no-store caching
  and nosniff headers.
- Pickup requires at least one `pre_handoff` or `handoff` photo from either
  participant. Each explicitly acknowledges condition/accessories and confirms
  possession changed. Both confirmations complete a sale via
  `mark_listing_sold()`, or start a loan at `on_loan`.
- Only the borrower uploads `pre_return` photos while `on_loan`, then initiates
  return. Initiation starts `return_pending`; it does not confirm receipt.
  Only the owner uploads `post_return` photos while `return_pending`.
- Both participants review before/after evidence and send `action: accept`.
  The second confirmation completes the loan and calls the existing atomic
  `release_listing()` in the same transaction. Failure rolls back completion.
- Either participant can raise a specific issue before mutual completion.
  `disputed` persists the reason, keeps the item reserved, and blocks acceptance.
  No automatic charge occurs; simulated disclosures remain visible.
- Either participant can cancel a negotiating or reserved exchange with a
  specific reason, before either has confirmed pickup. A reserved item's
  release is atomic with cancellation; failure rolls back both. Cancellation
  reasons persist and retrying the same cancellation preserves its timestamp
  without releasing any newer exchange's reservation. Cancellation after the
  first pickup confirmation is rejected. No charge is triggered.
- `POST /api/exchanges/{id}/dispute` applies the same borrow/return-pending
  restrictions as `/return` with `action: issue`. Retrying the same reason
  through either endpoint preserves the original disputed timestamp. Dispute
  resolution remains manual.
- Existing per-exchange write locks serialize uploads/confirmations. Confirmation
  retries preserve timestamps. Retrying an old completed return cannot release
  another exchange's newer reservation.

## Persistence and API additions

No shared schema change is needed. The existing `Evidence.acknowledged_by` JSON
records the timestamp of the combined condition acknowledgment and possession
confirmation on every reviewed photo. Those acts happen together through the
existing `/handoff` body `{confirm: true, accept_condition: true}` or return
`action: accept`. Standalone acknowledgment actions are not exposed. The locked
offer revision retains the agreed condition/accessories. Fresh dict assignment
persists SQLAlchemy JSON updates.

Finish all pickup uploads before either confirms. Borrower before-return photos
freeze at initiation; finish all owner after-return uploads before either
accepts. Once a participant confirms, the stage's evidence freezes so both review
the same record. Evidence files, timestamps, status, and dispute reason survive
new application instances using the same database and upload directory.

`GET /api/exchanges/{id}` adds `confirmations` and `max_upload_bytes` for the UI.
Each confirmation has `stage` (`handoff`/`return`), `participant_id`,
`condition_acknowledged_at`, `confirmed_at`, and `evidence_ids`. The timestamps
describe the same combined action.

The evidence-file endpoint retains its default image-byte response. Optional
`?preview=1` returns authenticated JSON `{data_url: "data:image/jpeg;base64,..."}`
with a small 480px preview. This uses the existing `window.api` JSON helper
without changing shared authentication/browser files or exposing public storage.
Previews strip metadata; original bytes remain private.

## Teammate dependencies

**Resolved:** `Pillow==12.3.0` is pinned in `requirements.txt` and installed in
the project's `.venv`. Install the normal environment using
`.venv/bin/python -m pip install -r requirements.txt`; photo validation and
previews no longer require `/tmp/campus-current-images` or a custom
`PYTHONPATH`. JPEG and WebP decoder support was verified in this installation.
Without the dependency installed, upload/preview validation still fails closed
with `503 image_validation_unavailable`. No models/migrations need modification.
Person 1 still needs to add the response/preview semantics to shared contracts.

**Resolved at the user's request:**
`tests/test_api_errors.py::test_exchange_auth_and_errors_use_real_records`
replaces the obsolete fixture/`501` assertions with auth/error-contract checks:
anonymous list `401`, authenticated empty list `{exchanges: []}`, missing
exchange reads/writes `404`, and invalid create JSON `400 validation_error`
with errors for the required listing and mode fields. Running
`.venv/bin/python -m pytest -q tests/test_api_errors.py tests/test_exchanges.py tests/test_reviews.py`
reported **111 passed**, with four existing Flask-SQLAlchemy migration
deprecation warnings. The historical failure counts elsewhere in this document
predate this correction. Existing Person 4 tests cover these routes' privacy
and state rules.

Latest `main` includes Person 1's Supabase storage adapter. The browser rehearsals
used local storage and labeled sandbox auth; live PostgreSQL and Supabase sessions
were not exercised. Person 2 matching/pricing and Person 3 marketplace work remain
outside this task.

## Preview and manual rehearsal

Use README setup, including installing the updated `requirements.txt`. The
preview explicitly selects `APP_ENV=development` so its sandbox remains
compatible with the shared production configuration guard. Normal preview
startup is:

```bash
.venv/bin/python -m server.exchanges.preview --port 5050
```

Open `http://127.0.0.1:5050/sign-in` (Codespaces: forwarded port 5050). Choose Bob
and open **My exchanges**. Use another browser profile/private window for Alice;
Charlie is the third party. Two tabs in one profile share one identity. The
runner migrates/seeds isolated labeled inventory, not completed transactions.
Restart with the same data directory to retain records and private files.

Windows: use `python -m server.exchanges.preview --port 5050` with the venv active.
The default preview data directory is `var/exchange-preview`.

1. Bob starts **Buy** for Alice's lamp. Propose a public pickup spot and explicit
   Eastern time; both accept the current revision. Without evidence, handoff is
   disabled. Upload pickup photos; both review condition/accessories, check both
   pickup boxes, and confirm. One confirmation keeps **Reserved**; both make
   **Completed** and **Sold**.
2. Bob starts **Borrow** for Alice's suit. Set fee $15, value $200, simulated
   deposit $60, pickup, return spot/deadline. Alice explicitly acknowledges the
   $140 not covered. Both accept; no real funds move. Upload pickup evidence and
   confirm from both sessions: **On loan**, item still reserved.
3. Bob uploads **Before return (borrower)** photos and initiates return. Both
   show **Return pending**. Alice uploads **After return (owner)** photos. Both
   review before/after evidence and confirm return. Only mutual confirmation
   completes the loan and makes the item available. Reload/restart to verify
   saved photos, acknowledgments, confirmations, and status.
4. For another loan at **Return pending**, raise a specific issue before both
   accept. Both show **Disputed** and the reason. The item remains reserved;
   return acceptance returns `409`; no charge is triggered.
5. Charlie cannot open the room, evidence metadata, original bytes, or preview
   (`403`). Anonymous photo access is `401`. Try a corrupt image, oversized file,
   missing evidence, owner initiation, and repeated confirmations.
6. Start another exchange and use **Cancel before pickup**, first during
   negotiation and then after reservation. A reason is required; both sessions
   show **Cancelled** and the reserved item becomes available. The action is
   unavailable once either participant confirms pickup.

## Changed files

`server/exchanges/routes.py`, new `images.py` and `lifecycle.py`;
`templates/exchanges/room.html`, `_styles.html`; `static/js/exchanges.js`;
`tests/test_exchanges.py`; and this document.

Pre-existing edits in `migrations/env.py`, `server/models/exchange.py`, and the
untracked file named `ervation"` were preserved.

## Checks actually run

- Baseline relevant suite: **73 passed** before the new endpoint tests.
- `.venv/bin/python -m pip install --target /tmp/campus-current-images Pillow`:
  **Pillow 12.3.0 installed** after approved network access.
- `PYTHONPATH=/tmp/campus-current-images .venv/bin/python -m pytest -q tests/test_exchanges.py tests/test_reservation.py tests/test_storage.py tests/test_auth.py`:
  **102 passed**. Includes negotiation regressions, unauthorized original/preview
  reads, invalid image content/size/dimensions, evidence/role/state gates,
  duplicate/concurrent confirmations, release rollback, safe old-loan retries,
  and multiple fresh application instances on persistent SQLite/files.
- `PYTHONPATH=/tmp/campus-current-images .venv/bin/python -m pytest -q`:
  **130 passed, 1 failed**: the obsolete Person 1 fixture/stub test above.
  The existing migration `get_engine()` deprecation warning remains.
- `node --check static/js/exchanges.js`,
  `.venv/bin/python -m compileall -q server/exchanges tests/test_exchanges.py`, and
  `git diff --check`: **passed**.
- `PYTHONPATH=/tmp/campus-current-browser:/tmp/campus-current-images PLAYWRIGHT_BROWSERS_PATH=/tmp/campus-current-browsers python3 /tmp/campus-current-p4-lifecycle-browser.py`:
  **passed** after approved Chromium launch. Separate Alice/Bob sessions completed
  one sale and one full loan, then exercised a disputed loan. Checked actual
  private previews, invalid-upload errors, missing-evidence UI gates, lender
  disclosure, Charlie/anonymous photo denial, persisted confirmations after
  reload, phone/desktop overflow, and absence of JavaScript errors. An initial
  rehearsal stopped at a preview-loading assertion; that test race was corrected
  before the successful complete run.
- Screenshots in `/tmp/campus-current-p4-lifecycle-artifacts/` were captured;
  the return-pending phone and disputed desktop views were visually inspected.

## Pull request integration checks

An isolated checkout combining `main` at `5523e45` with the Person 4 files and
the preview development-setting fix was tested without changing the shared
working files. With the temporary Pillow installation, the full Python suite
reported **260 passed, 1 failed, 1 skipped**. The failure is the obsolete shared
fixture/stub test described above. JavaScript syntax and Git whitespace checks
passed. An actual browser check against the combined checkout verified offer
revision updates, Alice's acceptance appearing for Bob after about five seconds,
and both sessions reaching Reserved after mutual acceptance. It also reproduced
the shared login across two normal tabs and reported no JavaScript page errors.
