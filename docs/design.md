# Design system (Person 3)

Frutiger Aero shell for Campus Current. One theme, six shared components,
consumed by the marketplace pages (Person 3) and the exchange pages (Person 4)
without redesign. Files: `static/css/theme.css`, `static/js/components.js`,
`templates/base.html`.

## Principles

- Sky-blue and leaf-green accents, glossy highlights, rounded translucent
  frames, gentle bubbles. No 3D library; everything is CSS gradients.
- Long text and every form control sit on an opaque surface (`--surface` is
  94% white, inputs are solid white). Translucent glass (`--glass`) is only for
  chrome: header, footer, short labels.
- Bubbles are decorative only: `position: fixed`, `z-index: -1`,
  `pointer-events: none`, `aria-hidden`, and static under reduced motion.
  Nothing animates behind dense text.
- Honest labels: fixture/stub data is purple-striped, anything money-related
  that is not real says "simulated", a profile badge shows the server's text
  verbatim and is green only when `verification_source === "supabase"`.
- Unknown is rendered as "unknown" (via `api.formatCents`/`api.formatTime`),
  never as `$0.00` or a made-up value.

## Typography

System stack only, no downloaded fonts, matching the mid-2000s Frutiger Aero
era (Windows Vista/7, Mac OS X, early iPhone):

```css
--font: "Segoe UI", "Lucida Grande", "Lucida Sans Unicode", Tahoma, Verdana, sans-serif;
```

Windows renders Segoe UI, macOS/iOS fall back to Lucida Grande, older systems
to Tahoma/Verdana. Body text is 1rem/1.5, plain weight, `--ink` on opaque
surfaces. Only large headings get polish: `h1` has a white top highlight plus a
faint sky shadow, the hero `h1` uses an ink-to-sky-900 gradient fill (both
colors are dark, so contrast stays high; it falls back to plain ink where
`background-clip: text` is unsupported), `h2` gets the highlight only. Form
fields, buttons, badges, and body copy have no shadows or gradients on text
except the white text on primary/leaf buttons, which keeps a 1px dark shadow
for legibility. No pixel, novelty, or display fonts anywhere.

## Tokens (`:root`)

| Token | Value | Use |
|---|---|---|
| `--sky-050 … --sky-900` | `#f3fbff` → `#0a4b7d` | Backgrounds, primary buttons, info badges. White text passes AA on `--sky-700` and darker. |
| `--leaf-100 … --leaf-900` | `#e9f9ea` → `#1d5f2a` | "Go" actions, verified badge, borrow badge. White text passes AA on `--leaf-700` and darker. |
| `--ink`, `--ink-soft`, `--ink-muted` | `#10304a`, `#2f4d66`, `#4f6b82` | Body text, secondary text, hints. All ≥ 5:1 on white. |
| `--sun`, `--sun-100`, `--sun-ink` | yellow family | Warnings, simulated-deposit notices, sandbox badge. |
| `--coral`, `--coral-100`, `--coral-ink` | red family | Errors, disputed state. |
| `--surface`, `--surface-solid`, `--glass` | white 94% / 100% / 55% | Cards, inputs, header. |
| `--r-sm` `--r-md` `--r-lg` `--r-pill` | 10 / 16 / 24 / 999px | Radii. |
| `--shadow-soft`, `--shadow-float`, `--shadow-inset` | | Card, dialog, gloss top line. |
| `--focus` | white ring + `--sky-900` ring | Every `:focus-visible`. |
| `--space-1 … --space-7` | 4 → 48px | Spacing scale. |
| `--dur`, `--ease` | 180ms | Transitions; zeroed under reduced motion. |

Breakpoints: below **720px** the header stacks (brand, menu toggle, nav list,
session); **720–999px** shows brand + session on one row with the nav on its
own row; from **1000px** everything is one row (brand tag hidden until
**1180px**). The home hero goes two-column at **860px**; spec rows collapse
below **480px**. Content max width is `--shell-max` (1040px) with 16px gutters.
The nav's `data-open` state only affects the stacked layout; wider widths
force the row layout even if the toggle was left open.

## Shell (`templates/base.html`)

Skip link → sticky glass `<header>` (brand, nav, `#session-status`) →
`<main id="main" class="shell-main" tabindex="-1">` → footer. Pages extend it
with blocks `title`, `page_id` (becomes `<body data-page>`), `content`,
`scripts`. Script order is `api.js` → `auth.js` → `components.js` → inline
shell script → `marketplace.js` → `{% block scripts %}`, so Person 4's
`exchanges.js` can use `window.api` and `window.components`.

Do not rename `#session-status`, `#nav-sign-in`, `.badge`, `.badge--warn`,
`.card`, `.simulated-notice`, `pre.json`: `auth.js` and
`templates/auth/sign_in.html` depend on them. Class-free `button`, `input`,
`select`, `textarea`, `label`, `fieldset` are fully styled so Person 1's
markup needs no classes.

## The six components

### 1. Button

CSS: `.btn` (also applied to bare `<button>` and `.button`) with modifiers
`.btn--primary` (deep sky, white text), `.btn--leaf` (go / accept),
`.btn--danger`, `.btn--ghost`, `.btn--sm`, `.btn--block`, `.btn--icon`.
States: hover brightens, `:active` presses down, `:disabled` fades,
`[aria-busy="true"]` hides the label and shows a spinner.

```js
const btn = components.button({ label: "Accept offer", variant: "leaf", onClick: accept });
components.setBusy(btn, true, "Accepting");   // spinner + disabled
components.setBusy(btn, false);
components.button({ label: "Back", href: "/exchanges" }); // <a> styled as a button
```

### 2. Field

CSS: `.field` > `.field__label` (with `.field__optional`), `.field__hint`,
control, `.field__error` (role=alert, hidden when empty). `.field__prefix`
with `data-prefix="$"` for money. `.field-row` lays fields side by side.
Checkbox/radio pills: `.choices` > `label.choice`. Key/value rows: `.kv-rows`.

```js
const fee = components.field({ id: "fee", label: "Rental fee", prefix: "$", hint: "Dollars; blank = unknown", attrs: { inputmode: "decimal" } });
form.append(fee.root);
const { cents, error } = components.dollarsToCents(fee.value()); // 1550 | null | error text
fee.setError("Must not be negative");  // sets aria-invalid + message
components.applyFieldErrors({ rental_fee_cents: fee, deposit_cents: dep }, err.fields); // from api.ApiError
```

Money: inputs take dollars, send integer cents, blank sends `null` (never 0).
Dates: `datetime-local` → `components.localToIso()` → ISO with `Z`
(assumes the browser is in the display zone; the hint says so).

### 3. Card

CSS: `.card` with gloss highlight; modifiers `--compact`, `--hero`, `--sky`,
`--leaf`, `--glass` (short text only), `--interactive` (hover lift). Parts:
`.card__media` (4:3, `--empty` shows "No photo yet"), `.card__header`,
`.card__title`, `.card__subtitle`, `.card__body`, `.card__footer`,
`a.card__link` (makes the whole card clickable, link text still readable).

```js
components.card({ title: "Navy suit 40R", subtitle: "formalwear", badges: [components.modeBadge("borrow")],
  media: { src: listing.public_photo_url, alt: "Photo of …" }, body: [...], footer: [...], variant: ["compact"], interactive: true });
```

### 4. Dialog

Native `<dialog class="dialog">` with `showModal()` (focus trap, Escape,
backdrop). Parts: `.dialog__header`, `.dialog__title`, `.dialog__body`,
`.dialog__footer`. Focus returns to the opener on close.

```js
const dlg = components.dialog({ title: "Confirm lower deposit", body: node,
  actions: [components.button({ label: "Cancel", onClick: () => dlg.close() }),
            components.button({ label: "I accept the uncovered amount", variant: "leaf", onClick: confirm })],
  onClose: (returnValue) => {} });
dlg.open(openerButton);
```

### 5. Badge

`.badge` (default = green "verified" look; use only for server-confirmed
facts), `--warn` (sandbox identity), `--info`, `--neutral`, `--error`,
`--fixture` (purple dashed stripes: stub/fixture data), `--sim` (simulated
money state), `--sale`, `--borrow`.

```js
components.profileBadge(profile)   // server badge text; green only if verification_source === "supabase"
components.modeBadge("sale")       // "For sale"
components.statusBadge("on_loan")  // every Listing/NeedRequest/Exchange status
components.fixtureBadge()          // "Fixture data"
```

### 6. Offer summary

`components.offerSummary(offer, opts)` renders an `OfferRevision` as
`.offer-summary`: head (title, mode badge, "Revision n", fixture badge if the
id is `fixture-*`), a `<dl>` with separate rows for **rental fee**, **agreed
item value**, **deposit** (dollars and % of value), and **amount not covered**
(highlighted in yellow when > 0, using the server's `uncovered_value_cents`,
never recomputed), pickup/return meeting + times, condition snapshot, both
acceptance states, the lender's lower-deposit acknowledgment state when
deposit < value, and the simulation label. Sale offers show the sale price
only and hide loan rows.

```js
components.offerSummary(detail.current_offer, {
  mode: detail.exchange.mode, listingTitle: listing.title, meetingSpots,
  depositStatus: detail.deposit_status, participants: detail.participants, fixture: detail.fixture });
```

## States and notices

```js
components.state.loading(container, "Loading…");
components.state.empty(container, { title, message, action });
components.state.error(container, err, { title, retry: fn });
components.notice("info" | "warn" | "error" | "leaf" | "fixture" | "sim", content);
components.simulationNotice();      // "Simulated: no real funds are reserved or charged."
components.toast("Saved", "leaf");
components.errorMessage(err);       // friendly text for api.ApiError codes
components.isAuthError(err);        // 401/403
```

`.skeleton` for placeholder blocks, `.spinner`, `.circulate` /
`components.circulationMark(spin)` for a tiny completed-exchange icon (static
under reduced motion).

## Circulation animation (completed exchange)

`components.circulation()` is the small Frutiger Aero scene from the brief: a
glossy bubble carries an item from person A (sky) to person B (leaf) along a
dotted arc, pops with a ring, and the item settles with a shimmer and two
sparkles. Plain CSS keyframes on inline SVG, 2.6 s, plays **once** (no loop).
Under `prefers-reduced-motion: reduce` every keyframe is disabled and the
still end state is shown (item already with person B, faint bubble, sparkles
on). It is its own box and must never be placed behind text or form fields.

Declarative (easiest; mounted automatically on load):

```html
<div data-circulation data-autoplay="true" data-replay="true" data-size="lg"
     aria-label="Exchange completed: the item moved to its new user"></div>
```

Programmatic (Person 4's "exchange completed" screen):

```js
const scene = components.circulation({ label: "Exchange completed", autoplay: false, replayButton: false, size: "lg" });
completedCard.prepend(scene.root);   // put it in its own row above the heading, not behind text
scene.play();                        // call when the completed status arrives; safe to call again
```

Options: `label` (accessible name, the root is `role="img"`), `autoplay`
(default true), `replayButton` (adds a small ghost "Replay" button; hidden
under reduced motion), `size` (`"sm"` 140px, default 200px, `"lg"` 280px).
`components.mountCirculations()` mounts any `[data-circulation]` added after
load. On the home page it sits above the headline (`.hero-mark`), plays once
on load, and has a Replay button.

Testing reduced motion: Chrome DevTools → Rendering panel → "Emulate CSS
media feature prefers-reduced-motion: reduce", or Windows Settings →
Accessibility → Visual effects → Animation effects off, then reload.

## Reference photo in the request flow (endpoint pending)

The home request box has an optional "Add a reference photo" file control.
Client validation: JPEG/PNG/WebP by MIME type; size limit is
`min(CAMPUS_CONFIG.max_upload_bytes, 5 MiB)` (the config key is not exposed
yet, so 5 MiB applies); a small preview with a Remove button. Text alone works
exactly as before.

Assumed endpoint (per `docs/ai-behavior.md`, Person 1 to confirm):
`POST /api/requests/normalize-photo`, verified user, **multipart** with
fields `photo` (file, required) and `text` (optional). Sent through
`api.post(path, FormData)`. Response `200 {"normalized": NormalizedRequest,
"fixture": false}`; errors use the shared envelope with `unsupported_image`
(400), `invalid_image` (400), `payload_too_large` (413). Optional assumed
response extra: `normalized.photo_attributes` (`{category?, type?, color?,
pattern?, style?}`); when absent the client derives it from the vision
whitelist.

Flow: photo present → photo endpoint (loading state "Analyzing photo…",
double-submit guard). Photo-derived attributes are turned into **pending
proposals** (`normalized.photo_proposals: [{name, value, status}]`) and
removed from the normalized category/specs, so nothing from the photo is part
of the request until the user accepts it. If the endpoint is missing
(404/405/501) or fails, a note says the photo was not used and the text
interpretation (or the manual form) is used instead.

Confirmation step (home page, `#confirm`, before any request exists). It
appears whenever there are photo proposals, the description is empty, or no
buy/borrow/service mode was interpreted. It contains:
- a required description textarea ("Add a few words about what you need" is
  shown beside it while empty);
- the proposals list: each attribute shows a "from photo" badge with
  **Accept** / **Dismiss** (and Change afterwards), plus Accept all / Dismiss
  all. Accepting sets the category or adds a preferred-specification row the
  user can still edit; dismissed proposals are never sent;
- the same editable interpretation form as the results page with the mode
  choice marked required ("Choose buy, borrow, or a service." beside it);
- a live summary line and a **Find matches** button that stays disabled until
  the description, a mode, and every proposal decision are present. Money and
  date validation is the same as for text requests and runs on submit.
Find matches then creates the request (`POST /api/requests`) with the
confirmed values and `photo_proposals` statuses recorded in `normalized`, and
redirects to results. Text requests whose interpretation already has a mode
skip this step exactly as before. On the results page only *accepted*
proposals are marked, with a neutral "from photo (accepted)" badge. The photo
is never stored, never sent anywhere else, and never appears on request cards
or the public feed.

## Services (implemented against Person 1's contract)

Services are a third listing kind on the real endpoints (docs/contracts.md,
merged from p1-services). No sample data remains. Shape used by the UI:

- Listing:  exactly ;  is one of
  , ,  (with a space);   required;  (0 allowed),   (1–1440),  (nonempty; one must fit the
  duration). Item fields are not sent (the server rejects them), including
  , so the meeting-spot picker hides in service mode. A
  photo may still be uploaded afterwards via the photo endpoint.
- NeedRequest:  exactly ,  a
  service category, ///  null or omitted, optional  and private
  . The public view adds .

Behavior: the listing form's **Service** pill is exclusive and shows the
service category, price, session length, and availability windows, hiding
condition, photo-independent item fields, specs, accessories, defects, sale and
borrowing terms, and meeting spots; client validation mirrors the server
(description required, windows nonempty and long enough). Listing detail
renders a service layout with price, session length, category, and windows,
no deposit section, and a disabled "Request this service" placeholder. All
cards use the teal  "Service" badge. In the interpretation
form (confirmation step and results) "A service" is exclusive with buy/borrow,
switches the category list to the eight service categories, hides deposit and
borrowing dates, and shows optional session length and private time windows;
/ build bodies that omit the rejected
fields. The feed shows "Needs a service" plus the session length and a
"Needs a service" filter.

Mismatches found against the earlier assumption (all resolved in the UI):
field names are prefixed  (,
,  on listings and
 on requests); there is no  field, the kind is
;  has a space; description and windows are
required; duration is 1–1440 not 5–720; meeting spots are rejected.

## Home "How it works" (implemented)

Below the request box: four steps on opaque step cards with inline SVG icons
(describe, matches with reasons, agree on price and deposit, meet at a public
spot) and a simulated-money note. No numbers or impact claims.

## My listings (implemented; route pending)

Template `templates/marketplace/my_listings.html` (page `my-listings`) and
`initMyListings` in `marketplace.js`. Person 1 needs to add
`@bp.get("/listings/mine")` rendering it in `server/routes/pages.py`; until
then `/listings/mine` is served by the listing-detail route and the script
mounts the same view there. Flow: redirect to `/sign-in` without a token;
identity from `GET /api/me`; listings from
`GET /api/listings?owner_id=<me>&status=all` (filtered again by `owner_id`
client-side); a Show filter (All / Items / Services, `aria-pressed` buttons
with counts) above tabs Active (available, reserved) and Past (sold,
withdrawn), whose counts follow the filter. Services come from the same
endpoint and carry the teal **Service** badge, price per session with the
duration, and the service category. Listing status is the contract's
`available | reserved | sold | withdrawn` for every kind: a reserved service
is shown as **Scheduled** (both participants accepted, so the session holds
the listing's single reservation) with "Session scheduled; manage it in the
exchange"; completion releases it back to Available. "Completed" is an
exchange status and lives on My exchanges, not on the listing card.
Withdraw only on available listings, confirmed in a `components.dialog`, then
`PATCH /api/listings/{id} {"status": "withdrawn"}`; `409 listing_locked` and
`403` are shown inside the dialog. Withdrawn listings get a **Relist** button
(`PATCH {"status": "available"}`). An in-flight set blocks double clicks on both. "On
loan" is not a listing status (the listing stays `reserved` during a loan), so
reserved cards say "Reserved or on loan; manage it in the exchange". The nav
shows "My listings" only when a token is present.

## Public request feed (implemented)

`/requests` (page `requests-feed`): `GET /api/requests` already returns only
`visibility=public` + `status=open` in the sanitized shape, so the page shows
exactly those fields: category and specs, buy/borrow, `needed_by_date`
(formatted as a plain date, never shifted by time zone), campus area, budget,
requester display name and server badge, and the posting time in Eastern.
Filters (buy/borrow, campus area built from the loaded data) are client-side.
Signed-in users see a disabled placeholder **I have this** (Person 4 wires it
to `POST /api/exchanges`); the requester sees "Your request" and a link to
their results; anonymous visitors see "Sign in to respond". States: loading,
"No open requests right now", "No requests match these filters" with a clear
button, and an error with retry.

## Header navigation widths

- < 720px: hamburger toggle, links stacked when open.
- 720–1179px: brand and session on row one, all links on one centered row
  with slightly tighter pills. The `<nav>` element (not the `ul`) is the grid
  item and is placed in the `nav` area with `min-width: 0`; the brand column
  is `minmax(0, 1fr)` so the nowrap link row can never widen it (that was
  the cause of "Account" wrapping and of page overflow).
- ≥ 1180px: brand, links, session on a single row.

## Accessibility rules

- Headings that receive programmatic focus (`h1`/`h2` with `tabindex="-1"`,
  e.g. My listings on load, the interpretation heading after Update results)
  show the focus ring only once the user has pressed a key:
  `components.js` records the last input kind on `html[data-input]`, and
  the ring rule is scoped to `data-input="keyboard"`. Pointer users never see
  a box on page load; keyboard users keep a visible ring.

- Every interactive element shows `--focus` on `:focus-visible`.
- Mobile nav toggle has `aria-expanded` and `aria-controls`.
- Loading regions set `aria-busy`; status text uses `aria-live="polite"`;
  errors use `role="alert"` and receive focus.
- After interpretation renders, focus moves to its heading (`tabindex="-1"`).
- `prefers-reduced-motion: reduce` zeroes animations and transitions, stops the
  bubbles, and disables the card hover lift.
- All server text goes through `textContent` (`components.el` with `text:`).
  `html:` is for static, trusted markup only.

## Home → results journey (implemented)

1. Not signed in: request box shows the sign-in notice and the submit is
   disabled. Listings still load for browsing.
2. Signed in: text → `POST /api/requests/normalize` → `POST /api/requests` →
   redirect to `/results/{id}`. If normalize fails (non-auth error) the
   request is created with `source: "manual"` and all-unknown fields; nothing
   is guessed. If the interpreter's values fail server validation, the request
   is re-created with those values cleared and a follow-up note saying so.
   When the interpreter gives no mode, both modes are stored as a search
   preference and shown as "needs confirmation".
3. Results page, top: the interpretation as an editable form (`buildInterpretationForm`
   in `marketplace.js`). Buy/borrow pills (at least one required), category,
   required and preferred specs as key/value rows, budget and affordable
   deposit as separate dollar fields, needed-by and borrowing dates, campus
   area. Null values show an "unknown" badge and an "unknown" placeholder;
   ambiguous dates and an unconfirmed mode show "needs confirmation".
   Follow-up questions are listed above the form. "Update results" →
   `PATCH /api/requests/{id}` (top-level fields plus the merged `normalized`
   object) → matches reload. Server `validation_error.fields` map back onto
   the inputs.
4. Results page, matches from `GET /api/requests/{id}/matches`:
   - fixture/stub responses get a purple dashed notice;
   - **Confirmed matches** grid: photo, title, mode, price or rental fee,
     owner's deposit proposal in dollars and percent (arithmetic on the
     listing's own `proposed_item_value_cents` × `collateral_percent`, labeled
     simulated), reasons (green check), shortcomings (red !), unknown required
     attributes (yellow ?), owner badge, "View listing";
   - **Needs confirmation before it counts**: a dashed yellow section
     (`.section--needs`, `.card--needs`) so these never read as confirmed;
   - **Excluded listings**: collapsed `<details>` with each shortcoming;
   - loading spinner, error state with retry.
5. No-match state (`.no-match`): shown only when both `confirmed` and
   `needs_confirmation` are empty. It lists the stored requirements as chips
   (`.chips`/`.chip`), summarizes the matcher's own exclusion reasons from
   `rejected` (never invented), and offers an explicit **Publish Request**
   button. Clicking opens a `components.dialog` preview with two
   `.privacy-list` blocks: "Will be public" (who, category, required and
   preferred details, buy/borrow, budget, needed-by date only, campus area,
   mirroring the server's public view) and "Stays private" (original wording,
   exact time, borrowing dates, pickup windows, deposit limit, contact).
   "Publish now" calls `POST /api/requests/{id}/publish` once (a `publishing`
   guard blocks repeat clicks), then shows a success notice with a link to
   `/requests` and the exact `public_preview` the server returned. Errors stay
   inside the dialog with both buttons re-enabled. An already-public request
   shows the success state instead of the button.
   Dev aid: `/results/{id}?preview=no-match` renders the no-match state with
   real results hidden and a visible "Preview mode" notice, because the stub
   matcher never returns an empty result.
6. Access: the results page needs the requester's token. 401 → sign-in
   notice; 403/404 or a non-owner view → "This request is not available".

## Listing form and detail (implemented)

- `/listings/new` (page `listing-form`, heading "List an item or service"):
  the modes fieldset offers sale, borrow, and the exclusive Service pill;
  choosing Service shows category, price per session, session length, and
  time windows and hides condition, photo, specifications, accessories,
  defects, meeting spots, and every sale/borrow money field (deposit,
  collateral, agreed value). Item path: title and category (required),
  description, condition, photo (JPEG/PNG/WebP ≤ 5 MB, client preview),
  specifications (key/value rows), accessories and known defects (one per
  line), modes as pills (`sale`, `borrow`), and only the matching term groups
  are shown. Sale: asking price (required). Borrow: rental fee (blank or 0 =
  explicit free loan), agreed item value (required), deposit percent (number
  input + `input.range` slider, default 100) with a live `.kv-list` showing
  the deposit in dollars and percent and the amount not covered, plus a
  warning when below full value; availability dates and notes. Meeting spots
  are pills from `GET /api/meeting-spots` with loading/empty/error states.
  Submit: client validation → `POST /api/listings` → `POST
  /api/listings/{id}/photo` (if a file was chosen) → `/listings/{id}?created=1`
  (or `?photo=failed` when only the upload failed). A `submitting` guard and
  `aria-busy` block double submits; server `validation_error.fields` map back
  onto inputs. A simulated-money notice sits above the form.
- `/listings/{id}` (page `listing-detail`): `.detail-grid` with photo (or
  "No photo provided"), badges (modes, status, demo account, "Your listing"),
  title, condition, description, specifications, accessories, defects; a
  Terms card listing sale price, rental fee, agreed item value, proposed
  deposit (dollars and percent) and amount not covered on separate rows, plus
  availability and the simulation notice; meeting spots resolved from
  `/api/meeting-spots`; owner card with the server's badge text and the
  exchange entry point (below). States: loading, 404 "Listing not found",
  error with retry.

## Exchange entry points (implemented)

- **Start exchange** (items) / **Request this service** (services) on
  `/listings/{id}`, built by `exchangeEntry()` in `marketplace.js`. The live
  button appears only when `/api/me` returned 200 for the current token (the
  server's idea of "verified"; sandbox users count), the user is not the owner,
  and the listing is `available` with at least one mode. Every other case is a
  hint instead: own listing, listing `reserved`/`sold`/`withdrawn`, signed out
  (a "Sign in to start an exchange" link), or a token the server rejected
  (401/403 message from `/api/me`).
- A listing with more than one mode shows a radio picker ("Buy it" /
  "Borrow it", reusing `.choices`/`.choice`); the button stays disabled with a
  `.field__todo` line until one is picked. Single-mode listings skip the
  picker. `?mode=sale|borrow` preselects.
- Click → `POST /api/exchanges {listing_id, mode[, source_request_id]}` with a
  `starting` guard and `aria-busy`, then `/exchanges/{id}` from the returned
  `exchange.id`. `?from_request=<id>` (added by the results page's View
  listing links) supplies `source_request_id`.
- Errors render in a `role="alert"` notice under the button and receive
  focus: `forbidden` (owner, shown as the server message, never as a sign-in
  prompt), 401 / `email_not_confirmed` / `domain_not_allowed` (sign-in link),
  `reservation_conflict` / `listing_unavailable` (no longer available, Reload
  listing button), `request_closed` / `validation_error.source_request_id` /
  404 request (could not link your request, "Start without linking" retries
  without it), `validation_error.mode` (reload), other validation (field
  list), 404 listing.
- **Post a listing for this** on `/requests` replaces "I have this": only the
  requester can start an exchange, so an owner answers by posting a listing
  at `/listings/new?from_request=<id>` and a note says the requester finds
  it through matching. The form fetches the public request and prefills only
  the modes, the category (service category for service requests), and a
  title seed; condition, specs, prices, and photo stay blank so nothing about
  the owner's item is invented. An info notice summarizes what was asked for;
  a 404 (closed or private request) leaves the form usable from scratch.

Service selectors support tutoring, proofreading, moving help, tech help, repair and
mending, bike repair, photography, and event help. Physical-item selectors use
formalwear, clothing, electronics, academic supplies, dorm essentials, event
equipment, outdoor gear, mobility, and tools. Existing custom categories remain
editable when loading older records. Category expansion changes no service lifecycle
or item price/deposit controls.

The home catalog now has Offer type (All, Buy, Borrow, Services) and Category
filters. Categories follow the selected offer type; requests use the existing
`GET /api/listings?mode=...&category=...` filters. Older asynchronous responses
cannot replace a newer selection. Service reference scenes appear on catalog,
match, owner, and detail cards without introducing item terms. Seeded licensed
reference photos describe fictional demo inventory, not a provider portrait or
proof of an item's exact model, condition, or accessories. Photo attribution
and the reference disclaimer remain visible in the listing description.

Service detail omits the item meeting-spot section, matching the service contract.
