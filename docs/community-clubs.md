# Community club handoff

Implementation branch: `p2-community-clubs`. No commit or push authorized.
Migration: `c706_community_clubs.py`, revision `c706community`, after
`c705exchangekeys`. Apply with `flask --app server.app db upgrade` to a reviewed
development target; existing listings/exchanges default to public/not-required.
The migration supports downgrade and preserves existing profiles.

## Fictional demo communities

Run the existing protected `seed-demo` on a dedicated development database.
It adds two clubs and five memberships idempotently, with scrypt code hashes.
No ratings, transactions, or verification claims are seeded. Codes below are
**fictional demo team codes**, not real organization credentials:

| Fictional demo club | Join code | Alice | Bob | Carol |
|---|---|---|---|---|
| Study Circle (fictional DEMO club) | `DEMO-STUDY-2026` | member | member | manager |
| Sharing Circle (fictional DEMO club) | `DEMO-SHARE-2026` | manager | joins by code | member |

Sandbox configuration must include `alice@unc.edu`, `bob@unc.edu`, and
`carol@unc.edu` for the three-user demo. Do not enable sandbox on production.
Existing catalog counts, listing terms and licensed files are preserved.

## Three-person approval demo

1. In Alice's sandbox account, create a listing with audience **Club only:
   Study Circle**. Enter ordinary item/service terms and upload a valid photo
   to publish; Club only is visibly labeled.
2. Bob (different account/session) opens it and starts an exchange. Negotiate
   complete terms with Alice. For a loan retain the full deposit or have Alice
   explicitly acknowledge a reduced deposit. For a service choose a time that
   fits its listed window.
3. Alice and Bob accept the same current revision. Observe **Waiting for club
   manager approval**, exchange negotiating, listing still available.
4. Carol signs in, opens **Your Account → Club manager review**, and refreshes.
   The narrow administrative card shows their display names, listing title,
   mode, status, and terms; it has no chat/evidence/location controls.
5. Carol can request changes with a note. Alice/Bob see the note, revise terms,
   and both reaccept; Carol refreshes and approves the latest displayed revision.
6. Approval atomically reserves the item or schedules the service. Participants
   finish through the existing pickup/return/service-completion screens. No
   real funds are held or charged; approval is not insurance or a safety claim.
7. Sign out and confirm the restricted listing is absent from browse/suggestions,
   direct detail/photo access and matching. An outsider cannot create a club
   listing or use Carol's manager review path.

## Profile demo

Your Account supports avatar, display name, 300-character bio, optional year,
private meeting preference, public club roles, public aggregate review/completion
counts, join-by-code, and an explicit history toggle. Public pages are at
`/profiles/{id}`. No avatar has an accessible placeholder. History defaults
private, and opted-in history excludes club titles and private terms.

## Integration/security limits

- No club CRUD, roster/contact endpoint, role management, membership removal UI,
  automatic discounts, or new payment/insurance behavior.
- Manager decisions require displayed `version` in addition to decision/note;
  stale responses cannot approve a newer offer accidentally.
- Club photos are stored in the **private** storage scope. The Flask media route
  checks membership; authenticated JSON previews let the shared API helper add
  the bearer header without putting secrets into URLs. Public catalog/avatar
  photos retain the public scope. Both buckets must remain separate.
- Code hashes are never serialized; demo plaintext codes exist only in the seed
  specification and this team handoff. Do not log request bodies at the proxy.
- Public aggregate service counts overlap owner-provided counts, as documented
  in contracts. Completion time uses existing `updated_at`; later changes to
  completed records can affect that date. A dedicated completion timestamp is
  deferred.
- Notifications keep their existing participant-only data and transitions.
  Manager pending review is refreshed from the account page; no new push or
  notification system is added.
- Production access/rate policies and operational abuse controls remain a
  deployment responsibility; this slice does not replace the existing auth.

Validation results are recorded in the final report; no live Gemini calls are
needed for this deterministic access/workflow change.

## Observed validation

- `STORAGE_BACKEND=local .venv/bin/python -m pytest -q`: **469 passed,
  1 skipped**, 110.83 seconds. PostgreSQL integration was skipped because
  `TEST_DATABASE_URL` was absent. Gemini unit tests remained mocked.
- `.venv/bin/python -m pytest -q tests/test_community.py`: **24 passed**.
- `.venv/bin/python -m pytest -q tests/test_community.py tests/test_demo_catalog.py tests/test_catalog.py tests/test_services.py`:
  **67 passed** after updating the existing seed expectation to permit the
  intentional public club memberships while preserving all other old fields.
- `node tests/browser_auth.test.cjs`: **7 passed**;
  `node tests/browser_shell.test.cjs`: **6 passed**;
  `node tests/browser_discovery.test.cjs`: **3 passed**.
- `node --check` passed for all 11 files under `static/js/`.
- `git diff --check` passed; repository conflict-marker search found none.

Actual HTTP/browser smoke used a migrated, seeded **temporary local SQLite
  database**, never the shared development database. Alice created a restricted
  demo suit listing through HTTP with its licensed photo; Bob negotiated and
  both accepted; Carol requested changes; Bob revised the pickup time; both
  reaccepted revision 3; Carol approved in Chrome. Observed exchange status
  `reserved`, club review `approved`, listing status `reserved`, and matching
  active exchange identity. Before approval the listing remained available.
  Anonymous restricted listing/photo reads returned 404. The manager screen
  exposed the limited review card and no chat, evidence, or private locations.

Chrome also verified profile editing, public profile rendering, club audience
choices, manager notes, and the waiting-for-approval state. Browser file upload
could not be exercised because Chrome's extension file-URL permission was
unavailable; upload validation/replacement and actual local photo publication
were exercised through Flask tests and HTTP instead. No live Gemini call was
needed. The smoke did not complete pickup/return or fabricate a review.

Changed files are limited to community models/migration/helpers/routes/seed,
existing access and exchange integration, profile and Aero UI integration,
contracts/handoff documentation, and focused regression tests. Implementation
remains uncommitted on `p2-community-clubs` pending team review.
