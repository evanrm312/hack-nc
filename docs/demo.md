# Person 4 workflow and review handoff

Private uploads, pickup, and return extend the existing negotiation/reservation
flow on `p4-exchanges`. Reviews, cancellation, and general `/dispute` remain
separate milestones; contested returns use `/return` with `action: issue`.

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

**Person 1:** pin `Pillow==12.3.0` in `requirements.txt` before integration, or
approve that narrow manifest change. Pillow was installed only under
`/tmp/campus-current-images` for this session; the shared manifest is untouched.
Without it, upload/preview validation fails closed with
`503 image_validation_unavailable`. No models/migrations need modification.
Add the response/preview semantics above to the shared contracts.

Person 1's existing
`tests/test_api_errors.py::test_exchange_stubs_are_labeled_fixtures_and_writes_501`
still expects the obsolete fixture exchanges and `501` writes from before P4-1.
Replace it with auth/error-contract checks: anonymous list `401`, authenticated
empty list `{exchanges: []}`, missing exchange reads/writes `404`, and invalid
create JSON `400 validation_error`. Existing Person 4 tests cover these routes'
privacy/state rules. The shared test was not edited.

Latest `main` includes Person 1's Supabase storage adapter. The browser rehearsals
used local storage and labeled sandbox auth; live PostgreSQL and Supabase sessions
were not exercised. Person 2 matching/pricing and Person 3 marketplace work remain
outside this task.

## Preview and manual rehearsal

Use README setup. The preview explicitly selects `APP_ENV=development` so its
sandbox remains compatible with the shared production configuration guard.
This session's temporary Pillow install works with:

```bash
PYTHONPATH=/tmp/campus-current-images .venv/bin/python -m server.exchanges.preview --port 5002 --data-dir /tmp/campus-current-p4-lifecycle-preview
```

Open `http://127.0.0.1:5002/sign-in` (Codespaces: forwarded port 5002). Choose Bob
and open **My exchanges**. Use another browser profile/private window for Alice;
Charlie is the third party. Two tabs in one profile share one identity. The
runner migrates/seeds isolated labeled inventory, not completed transactions.
Restart with the same data directory to retain records and private files.

After Person 1 installs the pinned dependency, normal preview startup is:

```bash
.venv/bin/python -m server.exchanges.preview --port 5001
```

Windows: use `python -m server.exchanges.preview --port 5001` with the venv active.
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
