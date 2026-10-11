# Aero refinement and meeting-spot handoff

Work remains on `ui/frutiger-aero-redesign`, based on the existing redesign
commit `b8f5cad` (backend base `9d778b5`). No shared models, API routes,
migrations, fixtures, seeds, or listing images are changed by this pass.

## Inspected references

The web research tool blocked Aero Archive, but direct Firefox access worked.
Screenshots and extracted page text are saved under
`/tmp/campus-aero-refinement/references/`.

| Source actually opened | Observed feature | Choice in this interface |
| --- | --- | --- |
| https://frutigeraeroarchive.org/resources | Nature wallpaper; tightly grouped navigation; outlined translucent panels; narrow reflective header bands; an actual Segoe UI/Tahoma/Geneva/Verdana CSS stack | Keep the sky/green environment and glossy chrome, while making content areas calm and navigation compact. This is a modern archive, not an original 2000s screenshot. |
| https://fontsinuse.com/tags/3741/2000s | Real examples span books, identities, and websites; they do not share one universal retro font | Use a readable humanist family for this product rather than imitate a novelty logo. |
| https://fontsinuse.com/uses/79154/shacknews-logo | December 2001 Aspirin wordmark in a screenshot of the January 2006 site; restrained metallic teal header framing | Keep polished trim and compact titles. Do not copy its lowercase logo or use Aspirin for form text. Screenshot is reference only, all rights reserved. |
| https://fontsinuse.com/uses/78453/the-typography-of-whitehouse-gov-2000-2026 | Inspected the October 2008 page and profile screenshots: compact information columns and clear heading/body separation; article describes the later use of Lucida Sans/Grande | Make the sidebar secondary, separate headings from supporting information, and retain open, readable body lettering. Screenshots are reference only, CC BY-NC-ND. |
| https://learn.microsoft.com/en-us/windows/win32/uxguide/vis-icons | Followed from Aero Archive; illustrated icon guidance distinguishes larger dimensional icons from simple toolbar symbols | Keep one original SVG family, polished icon frames, and real image thumbnails when available. |
| https://github.com/googlefonts/carlito | Inspected the README, attribution, Calibri metric compatibility, and OFL license | Previous pass used Carlito; retained as a licensed asset, superseded by Open Sans in the screenshot refinement below. |
| https://github.com/googlefonts/opensans | Inspected designer attribution, variable weight/width axes, and SIL OFL license | Use licensed Open Sans on Linux, with locally installed Segoe UI first, to approximate the user's Archive header reference. |

No new photography was needed. The existing real sky and leaf photographs
and their documented licenses remain in `static/assets/ASSETS.md`.

## Component audit and implemented changes

| Before | After | Interaction retained |
| --- | --- | --- |
| Bold request headline, repeated field question and long guidance | Regular-weight “What do you need?”; “Your request” label; shorter guidance | Text/photo normalization, editable confirmation, and required creation fields |
| Large right-side nature panel with repeated slogans and links | Small framed nature band; Recommended and Previous buys | Genuine catalog links and private exchange links |
| Source Sans 3, then Carlito with sharper/narrower forms | Segoe UI / locally bundled Open Sans with regular page headings and semibold titles/labels | Local Linux rendering and fallback stack |
| Condition, photo, specifications, accessories, and defects all expanded | Basics; optional Photos and details disclosures; Terms with optional Availability | Draft values survive mode toggles; invalid hidden fields are disabled and omitted from payloads |
| Nested green terms panels and one-column price fields | Plain aligned sections separated by a fine rule; paired related price controls on desktop | Sale, borrow, combined item modes, and exclusive service mode |
| Individual photo suggestions presented as decorative cards | Compact proposal rows with the same Accept/Dismiss decisions and useful bulk controls | Every proposed visual attribute still requires a decision |
| Generic account JSON disclosure only | Existing account information plus a read-only campus spot catalog | No fake preference save control or current-location collection |

Important copy changes:

- “Describe what you need” → “What do you need?”
- “buy · borrow · UNC” → “Buy · Borrow · UNC”
- “More use. Less unused.” → “Recommended” and “Previous buys”
- “Reuse · share · connect” → “UNC community exchange”
- Long input guidance → “Include size or model and budget. Review and edit the proposed details before searching.”
- “Optional. Public, well-lit campus spots.” → “Optional. Choose from the campus catalog. Access notes are recorded information; no location is guaranteed safe.” This removes an unsupported blanket lighting claim.
- Application-owned “optional”, “from photo”, and “unknown” badges → “Optional”, “From photo”, and “Unknown”. Protocol values, names, user text, and sample descriptions are preserved.

Adjacent Home catalog buttons were reduced to one New listing link. The
taskbar still supplies all destinations. Individual and bulk photo decisions,
accepting an offer, sending a message, and proposing different terms remain
distinct actions.

## Sidebar data interface

`window.campusDiscovery` exposes rendering adapters:

```js
renderRecommended(container, {
  kind: "catalog",
  items: [/* real Listing objects from GET /api/listings */]
});
renderPreviousBuys(container, {
  profileId: currentProfile.id,
  exchanges: [/* rows from participant-only GET /api/exchanges */]
});
```

The current Recommended provider is ordinary available catalog inventory,
explicitly labeled “Browsing suggestions from the catalog. Not personalized.”
There is no recommendation endpoint, relevance score, or invented explanation.
An algorithm provider can supply real Listing objects to the same renderer;
its identity/label must be explicitly integrated rather than inferred from
catalog order. Only three rows are shown; the full catalog remains below.

Previous buys keeps only `mode == "sale"`, `status == "completed"`, and
`requester_id == profileId`. Sales made by the user, loans, services, and
pending/cancelled exchanges are excluded. It uses the listing summary title
and exchange ID from the real endpoint. No purchase date or paid amount is
invented. Empty, signed-out, loading, and unavailable states are distinct.
An auth change clears displayed history immediately, and stale async responses
cannot restore it. On mobile the sidebar follows the request form.

## Meeting behavior currently supported

- `GET /api/meeting-spots` returns every active spot: `id`, `label`,
  `public_area`, `access_notes`. It has no coordinates or structured safety
  attributes. The new account reference renders these notes verbatim, unknowns
  honestly, and the list unranked.
- Item exchange dropdowns already include every returned active spot.
  Selecting one edits the offer draft; it does not finalize agreement.
- Item `POST /api/exchanges/{id}/offers` accepts `version`, current monetary
  and condition terms, `pickup_meeting_spot_id`, `pickup_at`, and borrow-only
  `return_meeting_spot_id`, `return_deadline`. Spot IDs must be active. Changed
  location terms create a revision and clear both acceptances; both users
  accept the current revision through `/accept`.
- Profiles currently have no bio, preference, or location field. `PATCH
  /api/me` only saves `display_name`. No persistent preference editor or
  private current-location form is presented in this refinement.
- Service offers reject physical pickup/return terms. No location fields are
  injected into service payloads.

## Proposed shared work — Evan

These are proposed contracts, not implemented endpoints or schema changes:

1. Add nullable `Profile.preferred_meeting_spot_id`, a MeetingSpot FK, in a
   **new** migration. Extend `PATCH /api/me` to partial updates accepting
   `{"preferred_meeting_spot_id":"active-id"}` or `null`; keep the existing
   display-name validation. Return the preference only in `/api/me`, excluding
   it from public profiles, listings, requests, and messages. The future editor
   should say “Optional campus meeting preference. Only you and participants
   in your private exchanges can see it. This is not your address or current
   location.” Participation access needs the explicit private detail contract
   below; do not expose it on public profile serialization.
2. Add an ExchangeLocation row unique on `(exchange_id, participant_id)`:
   `location_label` (manual campus landmark, max 160), nullable `latitude` and
   `longitude` as a validated pair, and `updated_at`. Participant identity
   comes from auth. Proposed `PUT /api/exchanges/{id}/my-location` accepts
   only the caller's fields; `DELETE` removes only that participant's row.
   Proposed participant-only GET `/api/exchanges/{id}/meeting-context`
   returns both location rows, participant preference IDs, and the catalog.
   Deny outsiders and preserve `private, no-store` / `nosniff` headers.
3. Define retention explicitly before shipping location collection: clear
   current-location rows on cancellation/completion; prohibit background
   collection and public serialization. UI copy: “Share a campus landmark
   with the other participant to compare meetup options for this exchange.
   It is private to this exchange.” Manual entry is the initial path; any
   geolocation request must follow an explicit user click.
4. If verified catalog coordinates become available, add nullable coordinate
   fields plus source/date, without rewriting existing seeds or inventing
   metadata. Optional safety facts should be nullable recorded attributes
   with source/date: lighting, cameras, public access, staffing, opening
   hours, and usual activity. Unknown is not false, and usual activity is
   not live crowd data. Existing `access_notes` remain verbatim.

Focused backend checks required: preference persistence across reloads;
inactive/missing spot rejection; private serialization; participant-only
location reads/writes; caller cannot overwrite the other row, including via
injected participant ID; valid coordinate pairs; cleanup on terminal states;
cache headers and service/item mode restrictions.

## Negotiation handoff — Sid

- Consume the proposed context API only after Evan implements it. Display
  every active spot. Missing coordinates mean an honest unranked list.
- If both participant and catalog coordinates exist, rank by the maximum
  participant straight-line distance, then total distance; use a preferred
  spot only as a tie-break preference. Label distances “Straight-line distance
  estimate”; never present them as walking routes or minutes. Do not hide
  valid catalog options or invent a safety score.
- Selecting an item suggestion edits the appropriate existing pickup/return
  draft. Keep revision checking, full offer submission, acceptance reset, and
  independent acceptance behavior. Changing a participant's transient location
  does not silently change the agreed spot.
- Services need a separate decision on whether optional meeting information
  belongs in a service offer. Existing service contracts have only price,
  duration, and scheduled time. Report this scope choice before adding a
  service location term; never reuse physical handoff fields.
- **Existing service UI defect observed in Firefox:** `exchanges.js`
  `loadInitial()` and `refresh()` request `/evidence` for every mode in
  `Promise.all`. Services correctly return `invalid_transition`, leaving
  `room-content` hidden. The controller also assumes a non-null current offer,
  `participants`, item condition/deposit fields, and item evidence metadata;
  the service detail contract does not supply those. Dispatch service rooms
  before these assumptions, support `current_offer: null`, and use service
  offer/accept/complete/cancel/dispute routes. The service listing proposal
  in `updateProposal()` also currently falls through to borrow wording.
  This requires Sid's behavioral changes; no workaround was added here.

Emily can wire the prepared catalog component and preference/location
controls after these APIs land. Aarush has no new recommendation-engine task
in this pass; a future provider needs a documented real data source.

## Review artifacts and verification

Baseline and after screenshots are in `/tmp/campus-aero-refinement/before/`
and `/tmp/campus-aero-refinement/after/`. The local feature preview is
`http://127.0.0.1:5057`; main continues separately on port 5055 when running.
The preview uses isolated SQLite and explicitly labeled sandbox identities.
State-changing journeys use a separate isolated SQLite copy on port 5059,
local Storage, and separate uploads. No shared database connection or seed
command is used for this work.

Python: 285 passed, 1 skipped (dedicated `TEST_DATABASE_URL` unavailable).
External providers are mocked in the Python suite. Node auth, launcher,
and sidebar tests: 13 passed. All JavaScript files passed `node --check`.
`git diff --check` passed. No backend behavior was added, so there are no new
backend authorization/persistence tests for the proposed location contracts.

Firefox UI walkthroughs: 92 assertions passed (66 layout/auth/menu/form
checks, 14 request/listing/Storage/message journey checks, 12 populated
history/catalog/mode-creation/reduced-motion/fallback checks). Widths were
1440, 1024, and 390px. The before/after walkthrough opened Home, sign-in,
listing form, public requests, My listings, My exchanges, item and service
listing details, results, no-match results, item exchange room, and service
exchange room. Inspecting a service room is not a passing service lifecycle
check: its existing controller defect is reported above. Screenshots were
opened and reviewed; the mobile focus-clearance and account notice wrapping
problems found in the first pass were corrected and rechecked.

The 14 journey checks used actual local APIs, SQLite and local Storage,
including photo normalization's manual fallback, required text/mode
confirmation, request creation, the $80/$200 deposit constraint, sanitized
request publication, a service listing, public photo retrieval, and private
messages. The later checks created sale/borrow/combined listings. Purchase
history used an explicitly synthetic completed-sale fixture in the isolated
database; it is not evidence of a completed real transaction. Catalog tests
added separate QA spots, including an inactive spot, without editing existing
records or seeds.

One initial photo attempt actually reached live Gemini and returned category,
type, and color proposals: the intelligence module reads the environment key,
so setting the Flask config key to null was insufficient to disable it.
Subsequent journey checks explicitly cleared the key in the isolated preview
process and verified the manual fallback instead. No auth email was requested.
Live Supabase authentication, the full service UI lifecycle, saved profile
preferences, private participant locations, geographic ranking, and real
two-person exchange completion remain unverified or pending.

## Screenshot-directed typography and depth refinement

This follow-up starts from feature commit `36e271b`. The supplied Archive
header screenshot informs regular-weight, open humanist lettering. Direct
Firefox inspection of the Archive resource page confirmed its Segoe UI /
Tahoma / Geneva / Verdana stack and 400-weight text. The reference screenshot
was not turned into an image asset. Open Sans is losslessly compressed to
WOFF2, with its full OFL license and source recorded in `static/assets/ASSETS.md`.

The window frame now has 22px corners; the hero and dialogs 20px; buttons
12px; fields 11px. Rounded chrome, white upper-left bevels, shaded lower edges,
and contact shadows create thickness without moving text into perspective.
Conversation wells and fields are inset; catalog rows remain quiet inside
a rounded collection frame. Semibold labels and section titles soften the
previous bold treatment. Primary hover/pressed states retain depth.

Additional copy corrections include:

- `formalwear · condition good` → `Formalwear · Condition: Good`
- `category: formalwear`, `deposit up to` → `Category: Formalwear`, `Deposit up to`
- `needs confirmation`, `none known`, `required` → `Needs confirmation`, `None known`, `Required`
- `from photo (accepted)` → `From photo (accepted)`
- `Publish Request` → `Publish request`
- Missing exchange times previously appeared as `unknown Eastern`; now `Time not agreed`.
- Service status `scheduled` has the display label `Scheduled`.

Only known application enum values receive display mappings. Custom categories,
condition wording, titles, descriptions, specification values, and messages
remain unchanged. No CSS text transformation is used. Exchange changes in
Sid's JS file are display strings only; the pending service controller
integration described above remains pending.

Verification for this follow-up:

- Full Python suite: **285 passed, 1 skipped**. External Auth, Gemini, and
  Supabase Storage checks are mocked; dedicated `TEST_DATABASE_URL` is absent.
- Browser auth/shell/discovery helper tests: **13 passed, 0 failed, 0 skipped**.
- `node --check`: all **7** JS files. `git diff --check`: passed.
- Headless Firefox walkthrough: **66 passed** across 12 reachable page states
  and 1440/1024/390px views; menu focus/Escape, form errors, service/item field
  visibility, draft preservation, keyboard/taskbar clearance, sandbox auth
  refresh/navigation/sign-out. This is local sandbox auth, not live Supabase.
- Targeted Firefox follow-up: **18 passed** for real loaded font, normal-weight
  headings, rounded/beveled materials, sentence-case labels, unchanged listing
  title/description and custom condition text, reduced motion, fallback type,
  publish preview, Escape focus restoration, and dialog/taskbar clearance.
- The first targeted run found a too-tall tablet publish dialog; fixed by a
  constrained flex dialog with scrollable body and visible footer, then reran
  all 18 checks successfully. Preview opening was tested without publishing.

Baseline screenshots: `/tmp/campus-aero-softening/before/`.
After screenshots: `/tmp/campus-aero-softening/after/`.
Comparison: `/tmp/campus-aero-softening/review.html`.
Local feature preview: `http://127.0.0.1:5057`, using the existing isolated
SQLite preview database and local uploads. No shared database was modified;
no seed or sample files changed. No new data-creation journey or live external
service check was needed for this typography/material pass. Main remains
untouched; nothing was pushed, merged, or deployed.
