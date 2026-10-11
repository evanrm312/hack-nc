# Completion integration — campus-completion

## Scope and checkout

Baseline: `origin/main` **3fb6df2**, re-fetched unchanged on October 11, 2026.
Final functional code tested: **b4d6f77b80ff8530340936d6fd3b14e22cf61575**.
Documentation is committed separately afterward. All changes remain on the
feature branch; main and the older Aero worktree are untouched. No merge or deployment.

The existing Aero materials, typography, photographs, taskbar and framing remain.
Sample records, IDs, fixtures, seed scripts, asset files and applied migrations
have no diff. State-changing QA used only isolated SQLite and local uploads.
Before/after screenshots contain isolated QA records, not changes to shared inventory.

## Confirmed defects fixed

| Reproduction/source evidence | Fix |
|---|---|
| Listing POST publishes before photo upload | Private draft → decoded image upload → atomic publication; owner retry/resume |
| Photo replacement bypasses reserved/sold edit lock | Same listing lock for field and photo changes; replacement denied in those states |
| Mode filtering follows 200-row limit | SQL filter before limit in catalog and matching; 201 competing rows regression |
| Failed Supabase sign-out clears UI while SDK session survives refresh | Failure retains authenticated status; successful local sign-out clears SDK/API/private UI |
| Known mode + ambiguous dates bypass homepage review | Explicit date acknowledgement before creation; edits invalidate acknowledgement |
| Creation/message lost responses can duplicate records | Scoped creation keys; confirmed request form also reuses its key |
| Service room uses item controls / lacks service detail rendering | Separate remote/in-person service offer, scheduling and independent completion UI |
| Unchanged service offer POST always creates a revision | Same terms return existing revision, preserve acceptances and emit no duplicate alert |
| Partial local write / unknown Supabase upload result leaves no cleanup attempt | Remove partial local file; attempt remote generated-object cleanup after upload error |
| Gemini photo API returned manual fallback after provider 500 | Bounded transient-error retries; editable fallback preserved, no speculative model change |

Feature verification also caught duplicate condition-confirmation alerts: the
second acknowledgment re-emitted the first participant’s acknowledgment. The
hook now emits only the caller’s newly recorded confirmation; a sale handoff
regression proves one condition alert per participant.

Validation failures now return to editable request review instead of silently
clearing terms or changing modes. The standalone Exchanges creation area is
removed; listing/result context retains listing, mode and source request.
Specifications are collapsed disclosures with entered-value summaries and
error expansion. Repeated browsing notices are removed; sandbox identities
stay truthful and agreement controls retain the simulated-payment disclosure.
Listing copy says **Proposed item value**, not an already agreed value.

## Persisted functionality and contracts

See [contracts](../contracts.md#completion-branch-contracts).

- Image required for sale, borrow, combined and service publication. Actual
  JPEG/PNG/WebP decoding, bounded read, still-image/16MP limits. Failures remain
  private, preserve form/draft and remove newly stored files on commit failure.
  Direct status PATCH cannot expose a draft, including via withdrawn status.
- Recipient-owned notification records, read timestamps, unread count,
  transactional event generation, retry deduplication, no message text or
  actor self-notifications. Panel polls while visible and clears on auth changes.
- Private profile meetup preference, participant-owned temporary campus areas,
  catalog map/list proposal controls, explicit unknown safety metadata. Each
  participant updates only their own context. Four-decimal coordinates expire
  after 24 hours and are cleared at terminal states.
- Both accept an active catalog spot through item offers or independent
  in-person service fields. Location changes reset acceptances. Remote services
  remain supported; no item evidence/pickup/return fields apply to services.
- Internal sign-in destination validation, callback/rate-limit/unavailable
  messages, profile validation, shared session/network helper preservation.

## Sid review and ownership

Sid PRs **#7 and #14 are merged**; `origin/p4-exchanges` has no commits beyond
main. Item offer validation, low-collateral acknowledgement, stale versions,
reservation conflicts, participant-only data, evidence, sale pickup and borrow
return behavior remain covered and passing. No pending Sid PR was merged here.

Overlap resolved: shared dispatch remains mode-specific; notifications observe
successful item/service transactions; services keep their separate lifecycle
and UI. Unchanged service offer retries now follow the item offer convention.
The single-active-service-booking contract remains unchanged.

Owner review needed before merge:

- **Evan:** five forward migrations, draft/publication contract, retry keys,
  notification transaction hook, Storage cleanup/failure handling, location retention job and isolated PostgreSQL
  verification. Apply live migrations only after review.
- **Sid:** notification hook coverage/locking, service offer retry semantics,
  separate in-person fields and two-real-account lifecycle verification.
- **Emily:** compact forms, draft recovery, service room, notification panel,
  map/list keyboard behavior and screenshots.
- **Aarush:** bounded Gemini retries and the original user-reported reproduction
  if different from the observed transient provider failure.

A separate remote branch `catalog-assets-services` at **f7b83c5** appeared during
final fetch. It is not merged into main and was not pulled into this work.
It expands categories to eight and changes models, normalization, preview,
contracts/tests and catalog assets. Reconcile those overlapping files explicitly
if it lands: this baseline intentionally retains the current three categories.
Emily's category controls must follow any separately reviewed expansion.

## Verification actually run

| Check | Result | External dependencies |
|---|---|---|
| Full Python at b4d6f77 | **412 passed, 0 failed, 1 skipped** | Gemini/Supabase provider responses mocked; isolated SQLite/local storage real |
| Focused publication/exchange/service/location/notification suite at 7a93b2c | **146 passed** | Isolated data; mocked providers |
| Final notification ownership/condition acknowledgement tests at b4d6f77 | **9 passed** | Isolated data; mocked providers |
| Final service/location/notification tests including offer retry at def3034 | **26 passed** | Isolated data; mocked providers |
| Storage/publication fault-injection tests at 5f0c10f | **22 passed** | Local writes real; Supabase upload/cleanup mocked |
| Node auth, launcher and purchase-history harnesses at def3034 | **15 passed, 0 failed, 0 skipped** | DOM/SDK/network mocked |
| JS syntax | **11 files passed** | `node --check static/js/*.js` individually |
| Empty SQLite migration chain | **Passed inside full suite** | Through head c705exchangekeys; item/service schema columns verified |
| Firefox page journeys | **41/41 assertions passed** | Sandbox auth, isolated local API/storage, inference fallback |
| Two-account service/alerts/outsider journey, rerun at def3034 | **14/14 passed** | Alice/Bob/Charlie isolated sandbox identities, not real Supabase accounts |
| Draft failure/resume/retry and taskbar focus | **8/8 passed** | Corrupt image then valid image; same draft published |
| Reduced-motion, closed-service controls, unknown safety and layout | **9/9 passed** | Actual Firefox reduced-motion preference |
| Ambiguous-date acknowledgement + lost-response retry | **6/6 passed** | Gemini response mocked; request persistence/idempotency real |
| `git diff --check` | **Passed** | Working diff and baseline diff |
| Live text normalization API | **200, source gemini** | Real Gemini key server-side; sandbox API identity |
| Live multipart photo normalization API | **200, source gemini** | Real Gemini, existing licensed leaves photo, no persistence |

The full suite emits one existing Google SDK Python deprecation warning.
`TEST_DATABASE_URL` is unset: the dedicated PostgreSQL migration/persistence
test is skipped. Its draft privacy assertion was updated but not executed on PG.
No destructive tests used DATABASE_URL. Local image upload/read is live;
Supabase Storage write/read is **unverified**, not established by adapter mocks.
If remote upload and deletion both fail, cleanup is best effort; the listing
stays private and storage maintenance is required. A provider write completing
after a timed-out cleanup can also leave an orphan. This remains an external
Storage integration risk to verify before deployment.

Live photo normalization initially returned safe editable manual output after
provider 500. Later both routes succeeded using the existing configured model.
Later success does not prove retries caused recovery. Mocked tests cover retry
statuses; the default model order/SDK configuration is preserved. No broken
user-facing Gemini link was identified; the original reported action/error
was not supplied.

No user browser/session was accessible. Real UNC signup, magic-link callback,
refresh/expiry, returning sign-in, sign-out and a two-real-account exchange
remain **unverified**. No magic-link emails were requested. Exact confirmed
`unc.edu` enforcement and failed/successful sign-out are covered by automated
checks, which do not establish live Supabase behavior.

## Screenshots and local preview

Isolated preview: **http://127.0.0.1:5057**. Sandbox identities stay labeled.
The existing main preview on 5055 was not replaced. The preview process uses
`/tmp/campus-completion-qa/preview.sqlite3` and `/tmp/campus-completion-qa/uploads`.
Its reproduction script is `/tmp/campus-completion-qa/preview.py`; it clones
an existing isolated QA database only, never the shared application database.

Before: `/tmp/campus-completion-qa/before/`.
After: `/tmp/campus-completion-qa/after/`.
Matching home, listing-form, exchanges, account, requests and my-listings
screenshots exist at 1440 and 390px. Results, empty results, item/service detail
and rooms were checked at 1440, 1024 and 390px. Images were visually inspected;
focus/taskbar and layout problems found during the walkthrough were corrected.
Service safety and notification screenshots show the new private UI.
`draft-resume-390.png` is the resulting published detail after retry, not an
editor screenshot. Logs and assertion JSON are in the same QA directory.

Browser regression reproducible with externally installed Selenium/geckodriver:
`python tests/browser_request_review.py http://127.0.0.1:5057 /path/to/geckodriver`.
Only use that explicitly isolated preview; it creates one private QA request.
No new runtime or development package dependency was added.

## Migrations, sources and remaining gates

New revisions: **c701publication → c702notifications → c703locations →
c704creationkeys → c705exchangekeys**, after existing **b6c28d1f9a04**.
No applied migration was edited. No live migration or seed command ran.
After review, Evan must verify the live current revision, then run
`flask --app server.app db upgrade` and schedule
`flask --app server.app purge-exchange-locations` hourly. The last supplied
live revision was a44534641a4c; that state was not rechecked in this task.

Coordinate evidence: [official UNC map](https://maps.unc.edu/), its linked
Concept3D map 111 markers [Union](https://map.concept3d.com/?id=111#!m/1049190),
[Davis](https://map.concept3d.com/?id=111#!m/15974),
[Rams Head](https://map.concept3d.com/?id=111#!m/632618), inspected October 10.
Union/Davis coordinates are building references, **not verified entrance points**.
Lighting, cameras, staffing, public access and opening hours remain unknown
unless catalog metadata has a source. Recorded seed notes are unverified.
Exact entrance/safety documentation remains a campus-data handoff to Evan;
it must not be filled by inference.

Map tiles: OpenStreetMap, visible contributor attribution and normal caching,
no bulk download. [Tile policy](https://operations.osmfoundation.org/policies/tiles/)
and [attribution/license](https://www.openstreetmap.org/copyright) inspected.
All existing photographic assets and licenses remain unchanged; no generated
artwork or new bundled font.

Provider references inspected:
[Gemini models](https://ai.google.dev/gemini-api/docs/models),
[troubleshooting](https://ai.google.dev/gemini-api/docs/troubleshooting),
[Supabase sign-out](https://supabase.com/docs/reference/javascript/auth-signout)
and [sign-out scopes](https://supabase.com/docs/guides/auth/signout).

Keep the PR in draft until owner review, isolated PostgreSQL and live
Supabase auth/Storage checks finish. No claim of production readiness,
real charges, secured deposits, safety guarantees or personalized recommendations.
