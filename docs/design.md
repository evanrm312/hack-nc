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

## Accessibility rules

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

- `/listings/new` (page `listing-form`): title and category (required),
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
  `/api/meeting-spots`; owner card with the server's badge text and a disabled
  placeholder **Start exchange** button with a hint (Person 4 wires it to
  `POST /api/exchanges`). States: loading, 404 "Listing not found", error with
  retry.
