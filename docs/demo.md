# Transaction demo and handoff — Person 4

## Requirements review

P4-1 is implemented against the existing schema and APIs. The broader Person 4
completion goal (pickup, completed sale, active loan, return, and reviews) remains
separate work; a reservation is not presented as a completed exchange.

| Assigned requirement | Current behavior / evidence |
|---|---|
| Requester creates an exchange for an available, permitted listing | Real API records; ownership, unavailable-item, mode, and source-request tests |
| Private messages with polling | Participant-only reads/writes; five-second polling; text rendering; third-party `403` tests |
| Versioned offers and acceptance reset | New revision for any changed term; both acceptances and lender acknowledgment reset; immutable history |
| Mutual acceptance of the current revision | Integer version check; stale offers return `409`; duplicate acceptance is idempotent |
| Meeting selection | Active campus spots, explicit Eastern times, return after pickup, and required meeting details before acceptance |
| Simulated collateral disclosure | Fee, value, deposit, percentage, uncovered amount, and explicit lender-only acknowledgment; visible simulation labels |
| Atomic reservation using shared helpers | Concurrent request tests prove one winner, loser rollback, and no lost simultaneous acceptance |
| Third-party evidence privacy | Evidence metadata and bytes are participant-only; another exchange's evidence returns `404` |
| Pickup and return as separate tasks | P4-2 and P4-3 below; require Person 1's confirmation persistence contract |

Review fixes: acceptance and the lender checkbox are disabled for unsaved terms;
the submit handler also prevents bypassing that guard. Offer history preserves
expanded revisions and keyboard focus during polling. Fee-only form edits preserve
existing meeting seconds. Fractional-second meeting timestamps are rejected with
a clear validation error because the shared serializer only exposes whole seconds.
This avoids accepting or silently rounding a time users cannot review.

## Quick, isolated preview

After installing the README dependencies, run from the repository root:

```bash
.venv/bin/python -m server.exchanges.preview --port 5001
```

On Windows with the virtual environment active, use
`python -m server.exchanges.preview --port 5001`. The runner migrates and seeds
`var/exchange-preview/preview.sqlite3`, separate from the normal development DB.
It does not change `.env`, shared authentication, or shared seed code. Repeated
startup does not duplicate its Alice-owned inventory. No acceptances, reviews,
completed transactions, or invented message history are seeded.

Open `http://127.0.0.1:5001/sign-in`, choose Bob, then **My exchanges**. The
Alice-owned navy suit supports borrowing; the desk lamp supports buying. Both
are labeled demo inventory. The pages carry an explicit sandbox preview notice.
Choose Alice in a separate browser profile/private window to negotiate. Charlie
is the third-party account for checking denied room access.

In Codespaces, open port **5001** from the **Ports** tab. The review preview uses
5001 because 5000 was already occupied; the existing server was left untouched.
The preview is a local sandbox, not a production deployment. Close it with Ctrl+C.

## Implemented milestone: P4-1

The existing **My exchanges** navigation opens `/exchanges`. Each participant
can open a private room at `/exchanges/<id>` from that list. The pages use Flask
page routes already supplied by Person 1, Jinja templates extending Person 3's
`base.html`, the shared theme classes, and vanilla JavaScript through `window.api`.
Page-specific responsive layout lives in `templates/exchanges/_styles.html`;
the shared theme and shell are unchanged.

Exchanges, messages, offer revisions, and acceptance timestamps are stored in
the existing SQLAlchemy tables. The UI reads actual participant-scoped records,
not the old fixture payloads. A new conversation starts at `negotiating`, with
an unaccepted revision derived from the listing's proposals. Meeting details
remain unknown until selected. Unknown condition information stays unknown.

Both participants may counter-propose terms. Changes to price, fee, value,
deposit, condition/accessories/defects, dates, or locations create a new revision
and clear both current acceptances and the lender's acknowledgment. Old revisions
remain available in history. Resubmitting identical terms preserves acceptance.
The API accepts partial term updates; the page submits the complete form.

Acceptance requires a positive integer `version`, complete meeting details, and
an explicit lender boolean acknowledgment when the deposit is below agreed value.
Both participants must accept the same current revision. A per-exchange database
write lock serializes edits/acceptances on SQLite and PostgreSQL. The second
acceptance uses Person 1's `reserve_listing()` within that same transaction.
A competing reservation returns `409 reservation_conflict` and rolls back the
loser's acceptance. Repeat acceptance is idempotent. Reserved terms are locked.

All monetary terms use integer USD cents. All payments and deposits are visibly
simulated: **no real funds are reserved or charged**. No card data is collected.
No price reference is assigned automatically; the page says “Insufficient
comparable data.” Validated price-range integration remains Person 2's later task.

Private messages poll every five seconds while the room is visible. The optional
`after` cursor includes its boundary second because the shared timestamp format
has second precision; messages are deduplicated by ID in the page. Message bodies
and other user content are rendered as text. Participant checks protect all
exchange routes, including currently deferred actions and evidence reads.
Existing private evidence bytes use Person 1's authorization/storage helpers.
Authenticated responses carry `Cache-Control: private, no-store`.

## Local setup and opening the page

Use the actual environment setup in `README.md`, then:

```bash
flask --app server.app db upgrade
flask --app server.app seed-demo
flask --app server.app run --debug
```

Open `http://127.0.0.1:5000/sign-in`, choose a sandbox identity, then click
**My exchanges** or open `http://127.0.0.1:5000/exchanges` directly. Anonymous
visitors see a sign-in prompt. A signed-in member with no exchanges sees the
empty state and an available-listing selector.

Use separate browser profiles, or one normal window and one private window,
for Alice and Bob. Tokens are held in localStorage; two tabs in the same browser
profile share one identity. For third-party checks, add `charlie@unc.edu` to the
local `SANDBOX_USERS` value and restart the server. Sandbox accounts remain
explicitly labeled as not verified.

`seed-demo` creates campus meeting spots and labeled inventory owned by the
special `sandbox:demo-lender` profile. That profile is not one of the default
Alice/Bob login identities. For a two-user negotiation demo, create a listing
owned by Alice through the existing listing API. This is deliberately created
sample inventory, not a fabricated completed transaction:

```bash
curl -X POST http://127.0.0.1:5000/api/listings \
  -H 'Authorization: Bearer sandbox:alice@unc.edu' \
  -H 'Content-Type: application/json' \
  -d '{"title":"Navy suit (demo inventory for exchange QA)","category":"formalwear","description":"Sample inventory for a local prototype demonstration.","allowed_modes":["borrow","sale"],"sale_price_cents":9000,"rental_fee_cents":1500,"proposed_item_value_cents":20000,"collateral_percent":100,"condition":"good","accessories":["garment bag"],"known_defects":[]}'
```

The response supplies the actual listing ID. Copy it if you want to open
`/exchanges?listing_id=<id>&mode=borrow`; otherwise Bob can select the listing
by title under **Start an exchange**. The listing form/detail pages in this
checkout are still Person 3's stubs.

## Two-browser negotiation demo

1. Sign in as Bob, open **My exchanges**, select Alice's demo suit and **Borrow**,
   and click **Start private exchange**. Revision 1 shows the listing proposals;
   acceptance is disabled until meeting details are provided.
2. Copy the room URL to Alice's signed-in browser. Send a message from each side;
   wait up to five seconds or use **Refresh exchange** to see the other message.
3. In Bob's room, keep the rental fee at $15 and agreed value at $200. Propose a
   $60 simulated deposit, select public pickup/return spots, and enter explicit
   dates/times. Inputs and displayed times use America/New_York regardless of
   the browser's timezone. DST gaps/repeated hours require a different time.
4. Submit **Propose terms**. Revision 2 shows a 30% deposit, $140 not covered,
   and a $75 simulated fee-plus-deposit total. Both acceptances are empty.
5. Bob accepts revision 2. Alice changes the fee to $16 and proposes it. Revision
   3 clears Bob's acceptance. A direct API acceptance of version 2 returns
   `409 stale_offer`; the latest revision must be reviewed again.
6. Bob accepts revision 3. Alice sees the lender-only checkbox stating the $140
   not covered and that compensation is not guaranteed. Alice must explicitly
   check it, then accept revision 3. Both rooms show **Reserved** and a simulated
   deposit status. Offer editing is hidden; no real funds moved.
7. Open the room as Charlie. The room content remains hidden and the API returns
   `403` for exchange, messages, evidence list, and evidence bytes. Charlie's
   exchange list does not include Alice and Bob's room.
8. For a sale, create a second Alice-owned demo listing, start another room as
   Bob with **Buy**, agree on sale price and pickup, then accept from both sides.
   Loan/deposit/return fields are absent. The exchange reserves after both accept.

Pickup and return actions are not part of this milestone. Do not describe a
reserved exchange as a completed sale or loan. A participant calling these
deferred endpoints gets a clear `501`; unrelated callers get `403` first.

## Teammate integration

- **Person 3:** connect the listing-detail “Start exchange” action to
  `/exchanges?listing_id=<listing.id>&mode=sale|borrow`, optionally adding
  `&source_request_id=<owned-request.id>`. The page selects the real listing and
  mode, then the user explicitly starts the exchange. Alternatively, POST
  `/api/exchanges` with those same fields and navigate to `/exchanges/<response.exchange.id>`.
  A source request must belong to the signed-in requester. The shared navigation
  and both page routes already exist; no route or shell edits are needed.
- **Person 1:** replace the obsolete
  `tests/test_api_errors.py::test_exchange_stubs_are_labeled_fixtures_and_writes_501`
  assertion when integrating P4-1. It requires fixture reads and `501` writes for
  the endpoints now implemented. Its replacement should check unauthenticated
  list access (`401`), an authenticated empty list (`{"exchanges": []}`), a
  missing exchange/messages/evidence read (`404`), missing exchange writes
  (`404`), and invalid create JSON (`400 validation_error`), using the existing
  error-shape assertion helper. Person 4's permission/state tests are in
  `tests/test_exchanges.py`. No other shared test behavior needs to change.
  Concrete replacement for that one function (in Person 1's file):

  ```python
  def test_exchange_error_contract(client, alice):
      _assert_error_shape(client.get("/api/exchanges"), 401, "auth_required")
      assert client.get("/api/exchanges", headers=alice).get_json() == {"exchanges": []}
      for suffix in ("", "/messages", "/evidence", "/evidence/missing"):
          _assert_error_shape(client.get("/api/exchanges/missing" + suffix, headers=alice), 404, "not_found")
      for suffix in ("messages", "offers", "accept", "evidence", "handoff", "return", "review", "cancel", "dispute"):
          _assert_error_shape(client.post("/api/exchanges/missing/" + suffix, json={}, headers=alice), 404, "not_found")
      _assert_error_shape(client.post("/api/exchanges", json={}, headers=alice), 400, "validation_error")
  ```
- **Person 1:** deployed Supabase auth/storage and PostgreSQL verification remain
  P1-2 work. This implementation uses the existing helpers and schema unchanged.
- **Person 2:** grounded pricing and matching remain separate integrations. No
  invented price evidence, verification, ratings, or impact metrics were added.

## Separate follow-up tasks

- **P4-2 — Pickup:** private condition uploads; both participants acknowledge
  condition/accessories and confirm possession changed; sale becomes `completed`
  and marks the item sold, borrow becomes `on_loan`. Obtain Person 1's shared
  persistence contract for both handoff confirmations before implementing it.
  Test unauthorized photo access, missing evidence, duplicate confirmations,
  rejection of misdescription, and invalid status transitions.
- **P4-3 — Return:** before/after private condition evidence, borrower initiation,
  owner acknowledgment, and mutual confirmation; release the item only on valid
  completion. A specific contested issue becomes `disputed` and never triggers a
  charge. Agree on return-confirmation persistence with Person 1 first. Test
  missing evidence, duplicate requests, non-owner acceptance, and disputed returns.
- Reviews, cancellation, and dispute actions remain later work. Their stubs now
  enforce participant privacy before returning `501`.

## Checks actually run for P4-1

- `.venv/bin/python -m pytest -q` — **101 passed, 1 failed**, solely the obsolete
  Person 1 fixture/stub test described above. It remains unchanged under Person 1's
  ownership. All **50 exchange tests** passed, including concurrent HTTP requests
  for competing reservations, simultaneous participant acceptance, an offer edit
  racing acceptance, invalid transitions, exact meeting-time preservation, and
  preview isolation/idempotency.
- `node --check static/js/exchanges.js`, Python compilation, and
  `git diff --check` — passed.
- Temporary Playwright/Chromium tools under `/tmp` checked two participant
  sessions and a third account against a migrated, isolated SQLite database.
  Passed: buy/borrow through reservation; private polling; literal rendering of
  HTML-like message text; acceptance reset and stale rejection; lender-only
  acknowledgment; anonymous/empty/error states and failed-initial-load retry;
  America/New_York times with a Tokyo browser; 1280px desktop and 390px phone
  layouts without horizontal overflow; no JavaScript errors.
- A focused browser follow-up passed unsaved-draft preservation through polling,
  stale-draft blocking, visible invalid-deposit errors, Eastern DST gap/repeated-hour
  rejection, and visible keyboard focus.
- Requirements-review browser checks on port 5001 passed unsaved-acceptance
  blocking (including direct form submission), lender-checkbox blocking for a
  draft, second-precision time preservation, history expansion and focus through
  polls/term changes, clearing resolved draft errors, and preview labels. The
  buy/borrow reservation journey passed again on that server.
- Preview migration checks emitted the existing `get_engine()` deprecation warning
  from Person 1's `migrations/env.py`; that file was not changed by this work.
- Browser screenshots were captured and visually inspected under
  `/tmp/campus-current-browser-artifacts/`. No browser dependency or new service
  was added to the repository. PostgreSQL and deployed Supabase flows were not run.

## Fallback for the larger team demo

Use labeled sandbox identities locally if email setup is unavailable; this is
not real UNC email verification and must not be exposed as a public bypass.
If Gemini is unavailable, use Person 2's disclosed manual/stub interpretation
and have the user confirm missing attributes. The exchange demo itself needs
no Gemini call. Do not present stub matching as validated compatibility, fixture
price ranges as observed transactions, or an unfinished pickup/return as success.
