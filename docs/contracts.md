# API contracts (v1)

Maintained by Person 1. Propose changes here before changing code that other
people consume. Every example below is what the scaffold actually returns.

## Conventions

- IDs are opaque strings (UUID4 hex). Fixture ids are prefixed `fixture-`.
- All money is integer USD cents. `null` means unknown or not offered, never 0.
  Fee, agreed value, and deposit are separate fields and never derived from
  each other automatically.
- Timestamps are ISO 8601 UTC with a trailing `Z` (`2026-10-14T13:00:00Z`).
  Clients must send a timezone offset; naive timestamps are rejected. The UI
  displays America/New_York (`api.formatTime`).
- Error shape, every `/api/*` failure (400, 401, 403, 404, 405, 409, 413, 501, 503, 500):

```json
{"error": {"code": "validation_error", "message": "Invalid request", "fields": {"sale_price_cents": "must not be negative"}}}
```

- Auth: `Authorization: Bearer <token>`. Identity always comes from the token;
  any `owner_id` / `requester_id` / `status` in a request body is ignored.
  - sandbox mode: token is `sandbox:<email>` for an email listed in `SANDBOX_USERS`.
  - supabase mode: token is the Supabase access token from the magic-link session.
- Auth error codes: `auth_required` (401, no token), `invalid_token` (401),
  `email_not_confirmed` (403), `domain_not_allowed` (403), `auth_unavailable` (503).
- Stub responses carry a top-level `"fixture": true`. Fixture data is never
  presented as a real record.
- Browser code uses `window.api` from `static/js/api.js` only.

## Records

### Profile

The email address is never stored on the profile and never serialized.
`verification_source` and `is_demo` are a Person 1 extension of the brief so
sandbox/demo identities are labeled.

```json
{
  "id": "0f1c6b9f8a3e4c1b9a0d5e6f7a8b9c0d",
  "display_name": "Member 0f1c6b",
  "confirmed_email_domain": "unc.edu",
  "verification_source": "sandbox",
  "badge": "Sandbox identity (not verified)",
  "is_demo": true,
  "created_at": "2026-10-10T19:00:00Z"
}
```

`badge` is `"UNC email verified"` only when `verification_source == "supabase"`.
Other users see the same object without `created_at` (as `owner` / `requester`).

### Listing

```json
{
  "id": "4a0c…",
  "owner_id": "0f1c…",
  "owner": {"id": "0f1c…", "display_name": "Member 0f1c6b", "confirmed_email_domain": "unc.edu", "verification_source": "sandbox", "badge": "Sandbox identity (not verified)", "is_demo": true},
  "title": "Navy suit 40R",
  "category": "formalwear",
  "description": "Two-piece, worn twice.",
  "specifications": {"type": "suit", "jacket_size": "40R", "color": "navy"},
  "condition": "good",
  "accessories": ["garment bag"],
  "known_defects": [],
  "allowed_modes": ["borrow", "sale"],
  "sale_price_cents": 9000,
  "rental_fee_cents": 1500,
  "proposed_item_value_cents": 20000,
  "collateral_percent": 100,
  "availability": {"available_from": "2026-10-12T12:00:00Z", "available_until": "2026-10-16T22:00:00Z", "notes": "Most weekdays after 2pm for pickup"},
  "meeting_spot_ids": ["7d2e…"],
  "status": "available",
  "active_exchange_id": null,
  "public_photo_url": "/media/public/ab/ab12….png",
  "created_at": "2026-10-10T19:01:00Z",
  "updated_at": "2026-10-10T19:01:00Z"
}
```

- `allowed_modes`: non-empty subset of `["sale", "borrow"]` for items, or exactly
  `["service"]` for a service. Services cannot be combined with item modes.
- `condition`: one of `new`, `like_new`, `good`, `fair`, `worn`, or null.
- `status`: `draft` | `available` | `reserved` | `sold` | `withdrawn`. New listings
  remain private drafts until validated image publication. Only the reservation
  helper moves a listing to `reserved`/`sold`; owners may set `available`/`withdrawn`
  on editable published listings. PATCH cannot publish a draft.
- `"sale"` requires `sale_price_cents`; `"borrow"` requires
  `proposed_item_value_cents`. For borrow, a missing `rental_fee_cents` becomes
  `0` (explicit free loan) and a missing `collateral_percent` becomes `100`.
- `collateral_percent` is the owner's proposal (0-100). The deposit in cents is
  decided per offer revision, not here.

#### Service Listing (public view)

Services use the same listing endpoints and `allowed_modes: ["service"]`.
Categories are exactly `tutoring`, `proofreading`, `moving help`, `tech help`,
`repair and mending`, `bike repair`, `photography`, or `event help`.
`server.models.listing.SERVICE_CATEGORIES` is the backend source of truth;
these are category string values, requiring no database migration.
`service_price_cents` may be zero; `service_duration_minutes` is 1–1440;
`service_available_windows` is a nonempty list of offset-aware UTC intervals.
Item condition, collateral, deposit, agreed value, sale price, and rental fee
fields are rejected and omitted from service responses. Example `POST /api/listings`
body:

```json
{
  "title": "Calculus tutoring",
  "description": "One-on-one calculus help at the library.",
  "category": "tutoring",
  "allowed_modes": ["service"],
  "service_price_cents": 2500,
  "service_duration_minutes": 60,
  "service_available_windows": [{"start": "2030-10-12T12:00:00Z", "end": "2030-10-12T14:00:00Z"}]
}
```

Example published `200 {"listing": ...}` record after photo publication:

```json
{
  "id": "4a0c0000000000000000000000000001",
  "owner_id": "0f1c0000000000000000000000000001",
  "owner": {"id": "0f1c0000000000000000000000000001", "display_name": "Member 0f1c00", "confirmed_email_domain": "unc.edu", "verification_source": "sandbox", "badge": "Sandbox identity (not verified)", "is_demo": true},
  "title": "Calculus tutoring",
  "category": "tutoring",
  "description": "One-on-one calculus help at the library.",
  "allowed_modes": ["service"],
  "status": "available",
  "active_exchange_id": null,
  "public_photo_url": null,
  "created_at": "2030-10-10T19:01:00Z",
  "updated_at": "2030-10-10T19:01:00Z",
  "service_price_cents": 2500,
  "service_duration_minutes": 60,
  "service_available_windows": [{"start": "2030-10-12T12:00:00Z", "end": "2030-10-12T14:00:00Z"}]
}
```

### NeedRequest (owner view)

```json
{
  "id": "9b3f…",
  "requester_id": "77aa…",
  "original_text": "Borrow a navy 40R suit for an interview Wednesday, October 14, 2026. Pickup Tuesday 2-4pm; return Thursday by 6pm. Rental budget $40.",
  "normalized": {"source": "manual", "category": "formalwear", "required_specifications": {"type": "suit", "jacket_size": "40R"}, "preferred_specifications": {"color": "navy"}, "follow_up_questions": []},
  "modes": ["borrow"],
  "budget_cents": 4000,
  "max_deposit_cents": 8000,
  "needed_by": "2026-10-14T13:00:00Z",
  "use_start": "2026-10-13T18:00:00Z",
  "use_end": "2026-10-15T22:00:00Z",
  "pickup_windows": [{"start": "2026-10-13T18:00:00Z", "end": "2026-10-13T20:00:00Z"}],
  "area": "Central campus",
  "visibility": "private",
  "status": "draft",
  "created_at": "2026-10-10T19:02:00Z",
  "updated_at": "2026-10-10T19:02:00Z"
}
```

- `status`: `draft` | `open` | `fulfilled` | `cancelled` | `expired`.
- `visibility`: `private` | `public`. Publishing sets `public` + `open`.
- `budget_cents` (purchase/rental budget) and `max_deposit_cents` (deposit
  affordability) are separate constraints.

#### Service NeedRequest (owner view)

Service requests use `modes: ["service"]` and one of the eight service
categories in `normalized.category`. `max_deposit_cents`, loan dates, and pickup
windows are rejected and omitted. `service_duration_minutes` and
`service_time_windows` may be omitted when unknown; a missing constraint stays
unknown. Example `POST /api/requests` body:

```json
{
  "original_text": "I need an hour of calculus tutoring.",
  "normalized": {"source": "manual", "category": "tutoring", "required_specifications": {}, "preferred_specifications": {}},
  "modes": ["service"],
  "budget_cents": 3000,
  "needed_by": "2030-10-13T00:00:00Z",
  "service_duration_minutes": 60,
  "service_time_windows": [{"start": "2030-10-12T12:00:00Z", "end": "2030-10-12T14:00:00Z"}],
  "area": "Davis Library"
}
```

Example `201 {"request": ..., "view": "owner"}` record:

```json
{
  "id": "9b3f0000000000000000000000000001",
  "requester_id": "77aa0000000000000000000000000001",
  "original_text": "I need an hour of calculus tutoring.",
  "normalized": {"source": "manual", "category": "tutoring", "required_specifications": {}, "preferred_specifications": {}},
  "modes": ["service"],
  "budget_cents": 3000,
  "needed_by": "2030-10-13T00:00:00Z",
  "area": "Davis Library",
  "visibility": "private",
  "status": "draft",
  "created_at": "2030-10-10T19:02:00Z",
  "updated_at": "2030-10-10T19:02:00Z",
  "service_duration_minutes": 60,
  "service_time_windows": [{"start": "2030-10-12T12:00:00Z", "end": "2030-10-12T14:00:00Z"}]
}
```

### NeedRequest (sanitized public view)

No `original_text`, no `pickup_windows`, no `use_start`/`use_end`, no precise
`needed_by` time, no requester contact.

```json
{
  "id": "9b3f…",
  "requester": {"id": "77aa…", "display_name": "Member 77aa", "confirmed_email_domain": "unc.edu", "verification_source": "sandbox", "badge": "Sandbox identity (not verified)", "is_demo": true},
  "category": "formalwear",
  "modes": ["borrow"],
  "required_specifications": {"type": "suit", "jacket_size": "40R"},
  "preferred_specifications": {"color": "navy"},
  "budget_cents": 4000,
  "needed_by_date": "2026-10-14",
  "area": "Central campus",
  "status": "open",
  "created_at": "2026-10-10T19:02:00Z"
}
```

### NormalizedRequest (stored in `NeedRequest.normalized`; produced by `normalize_request`)

```json
{
  "source": "gemini",
  "modes": ["borrow"],
  "category": "formalwear",
  "required_specifications": {"type": "suit", "jacket_size": "40R"},
  "preferred_specifications": {"color": "navy"},
  "budget_cents": null,
  "max_deposit_cents": null,
  "needed_by": "2026-10-14T13:00:00Z",
  "use_start": null,
  "use_end": null,
  "area": null,
  "ambiguous_dates": [{"text": "2 a.m.", "proposed": "2026-10-14T06:00:00Z", "needs_confirmation": true}],
  "follow_up_questions": ["What is your trouser size?"],
  "original_text": "…"
}
```

`source` is `gemini` when validated Gemini output is available, otherwise
`manual` with unknown scalar fields set to `null`, empty specification maps,
and a follow-up explaining that the user must fill in the editable fields.
The user edits this object before searching; the server stores whatever they
confirm. Missing or invalid Gemini output never creates fixture data.

### Exchange

```json
{
  "id": "c1d2…",
  "listing_id": "4a0c…",
  "owner_id": "0f1c…",
  "requester_id": "77aa…",
  "source_request_id": "9b3f…",
  "mode": "borrow",
  "status": "negotiating",
  "current_offer_revision": 2,
  "cancellation_reason": null,
  "dispute_reason": null,
  "created_at": "2026-10-10T15:00:00Z",
  "updated_at": "2026-10-10T15:20:00Z"
}
```

Item `status`: `negotiating` | `reserved` | `on_loan` | `return_pending` |
`completed` | `disputed` | `cancelled`. Services use `negotiating` |
`scheduled` | `completed` | `cancelled` | `disputed` only.

#### Service Exchange

Service negotiation starts with `POST /api/exchanges` body
`{"listing_id":"4a0c0000000000000000000000000001","mode":"service","source_request_id":"9b3f0000000000000000000000000001"}`.
The response is `201 {"exchange": ServiceExchange, "current_offer": null}`.
Example service exchange record after both participants accept the current offer:

```json
{
  "id": "c1d20000000000000000000000000001",
  "listing_id": "4a0c0000000000000000000000000001",
  "owner_id": "0f1c0000000000000000000000000001",
  "requester_id": "77aa0000000000000000000000000001",
  "source_request_id": "9b3f0000000000000000000000000001",
  "mode": "service",
  "status": "scheduled",
  "current_offer_revision": 1,
  "cancellation_reason": null,
  "dispute_reason": null,
  "created_at": "2030-10-10T19:05:00Z",
  "updated_at": "2030-10-10T19:08:00Z",
  "owner_service_confirmed_at": null,
  "requester_service_confirmed_at": null,
  "payment_notice": "Simulated: no real funds are reserved or charged."
}
```

`POST /api/exchanges/{id}/offers` accepts
`{"service_price_cents":2500,"service_duration_minutes":60,"service_scheduled_at":"2030-10-12T12:00:00Z"}`.
The scheduled interval must fit a listing availability window. Example `offer`
record returned with `201 {"offer": ..., "exchange": ...}`:

```json
{
  "id": "e5f60000000000000000000000000001",
  "exchange_id": "c1d20000000000000000000000000001",
  "version": 1,
  "created_by": "0f1c0000000000000000000000000001",
  "owner_accepted_at": "2030-10-10T19:07:00Z",
  "requester_accepted_at": "2030-10-10T19:08:00Z",
  "created_at": "2030-10-10T19:06:00Z",
  "service_price_cents": 2500,
  "service_duration_minutes": 60,
  "service_scheduled_at": "2030-10-12T12:00:00Z"
}
```

Each participant calls `POST /api/exchanges/{id}/accept` with `{"version":1}`.
Both acceptances move `negotiating → scheduled` and reserve the listing; a
new offer creates a new revision with neither acceptance. Each participant then
calls `POST /api/exchanges/{id}/complete` with `{"confirm":true}` after the
session happened. Only the second confirmation moves `scheduled → completed`
and releases the listing. `POST /cancel` or `/dispute` accepts a nonempty
`{"reason":"..."}` and never charges funds. The price is a proposed service
fee in integer cents; no real payment is collected. Service responses omit
deposit status, item condition, collateral, agreed value, handoff, return,
and evidence fields. Service calls to `/handoff`, `/return`, or `/evidence`
return `409 invalid_transition`; nonparticipants receive `403`.
`GET /api/exchanges` includes all of the caller's sale, borrow, and service
exchanges without a mode query parameter. `GET /api/exchanges/{id}` returns the
service exchange and offers to its participants only.

Scheduling uses the listing's single active reservation. A service listing can
have only one scheduled booking at a time, even when two proposed appointments
do not overlap. A second exchange receives `409 reservation_conflict` when both
participants try to schedule it; completion, cancellation, or dispute releases
the reservation. There is no multi-appointment calendar in this scope.

### OfferRevision

```json
{
  "id": "e5f6…",
  "exchange_id": "c1d2…",
  "version": 2,
  "created_by": "77aa…",
  "sale_price_cents": null,
  "rental_fee_cents": 1500,
  "agreed_item_value_cents": 20000,
  "deposit_cents": 6000,
  "uncovered_value_cents": 14000,
  "lower_deposit_acknowledged": false,
  "condition_snapshot": {"condition": "good", "accessories": ["garment bag"], "known_defects": []},
  "pickup_meeting_spot_id": "7d2e…",
  "pickup_at": "2026-10-12T18:00:00Z",
  "return_meeting_spot_id": "7d2e…",
  "return_deadline": "2026-10-15T22:00:00Z",
  "pricing_range_version": null,
  "price_reference_id": null,
  "owner_accepted_at": null,
  "requester_accepted_at": "2026-10-10T15:20:00Z",
  "created_at": "2026-10-10T15:20:00Z"
}
```

- `uncovered_value_cents = max(agreed_item_value_cents - deposit_cents, 0)`.
- When `deposit_cents < agreed_item_value_cents`, `lower_deposit_acknowledged`
  must be true (set by the owner) before the owner's acceptance counts.
- `(exchange_id, version)` is unique. A new revision resets both acceptances.
- Sale offers use `sale_price_cents` only; loan fields must be null for sales.

### Message

```json
{"id": "m1…", "exchange_id": "c1d2…", "sender_id": "77aa…", "body": "Is it available Monday?", "created_at": "2026-10-10T15:05:00Z"}
```

### Evidence

```json
{"id": "ev1…", "exchange_id": "c1d2…", "uploader_id": "0f1c…", "stage": "pre_handoff", "content_type": "image/jpeg", "acknowledged_by": {"77aa…": "2026-10-12T18:05:00Z"}, "url": "/api/exchanges/c1d2…/evidence/ev1…", "created_at": "2026-10-12T17:50:00Z"}
```

`stage`: `pre_handoff` | `handoff` | `pre_return` | `post_return`. Bytes are
only served to participants through the `url` endpoint, never from `/media/`.

### Review

```json
{"id": "r1…", "exchange_id": "c1d2…", "reviewer_id": "77aa…", "reviewee_id": "0f1c…", "stars": 5, "structured_answers": {"description_accurate": "yes", "condition_as_agreed": "yes", "punctual": "yes", "communicative": "yes", "returned_on_time": "not_applicable"}, "comment": null, "created_at": "2026-10-16T12:00:00Z"}
```

Each structured answer is `yes` | `no` | `not_applicable`. `(exchange_id, reviewer_id)` is unique.

### MeetingSpot

```json
{"id": "7d2e…", "label": "Student Union main lobby", "public_area": "Pit / Union", "access_notes": "Open 7am-midnight; staffed info desk."}
```

### PriceReference

```json
{"id": "p1…", "category": "formalwear", "specifications": {"type": "two-piece suit"}, "condition": "good", "price_type": "rental", "duration_basis": "per_3_days", "lower_cents": 1000, "upper_cents": 3000, "sample_count": 8, "source": "FIXTURE: hand-labeled demo range, not observed platform transactions", "observed_from": "2026-08-01", "observed_to": "2026-09-30", "is_fixture": true, "version": 1, "created_at": "…"}
```

## Person 1 endpoints

### `GET /api/health` (public)

→ `200 {"status": "ok"}`. This checks HTTP availability only. The existing
`GET /healthz` route remains available for the deployment check.

### `GET /api/me` (verified)

→ `200 {"profile": Profile}`; `401`/`403` per the auth codes above.

### `PATCH /api/me` (verified)

Body `{"display_name": "Tar Heel"}` → `200 {"profile": Profile}`.

### `GET /api/listings` (public)

Query: `status` (default `available`; `all` for public statuses plus the caller’s private drafts), `category`,
`mode` (`sale`|`borrow`|`service`), `owner_id`. → `200 {"listings": [Listing]}`.

### `POST /api/listings` (verified)

Body: any Listing fields except `id`, `owner_id`, `owner`, `status`,
`active_exchange_id`, `public_photo_url`, timestamps. Required for draft creation: `title`,
`category`, `allowed_modes`, and applicable price/session terms. Publication also requires description and image (matrix below).

```json
{"title": "Navy suit 40R", "category": "formalwear", "allowed_modes": ["borrow", "sale"], "sale_price_cents": 9000, "rental_fee_cents": 1500, "proposed_item_value_cents": 20000, "collateral_percent": 100, "specifications": {"type": "suit", "jacket_size": "40R"}, "condition": "good", "meeting_spot_ids": ["7d2e…"]}
```

→ `201 {"listing": Listing}` (private draft); `400 validation_error` with per-field messages.

### `GET /api/listings/{id}` → `200 {"listing": Listing}` | `404`.

Published records are public; drafts require the owner’s token and appear
as `404` to everyone else.

### `PATCH /api/listings/{id}` (owner only)

Same fields as create, partial; published listings also accept `"status": "available"|"withdrawn"`. Drafts cannot change status through PATCH.
→ `200 {"listing": Listing}`; `403 forbidden` for a different user;
`409 listing_locked` while reserved/sold.

### `POST /api/listings/{id}/photo` (owner only)

Multipart field `photo` (decoded JPEG/PNG/WebP, ≤ `min(MAX_UPLOAD_BYTES, 5 MiB)`). Reserved/sold/draft listings reject this replacement route.
→ `200 {"listing": Listing}`; `400 unsupported_image`; `413 payload_too_large`.

### `GET /media/public/{path}` (public) — listing photo bytes.

### `GET /api/meeting-spots` (public) → `200 {"meeting_spots": [MeetingSpot]}`.

### `POST /api/requests/normalize` (verified)

Body `{"text": "I need a navy suit…"}` →
`200 {"normalized": NormalizedRequest, "fixture": false}`. Gemini results have
`source: "gemini"` and are validated before return. Without a key or when the
provider fails, the editable fallback has `source: "manual"`, unknown fields
set to `null`, empty specification maps, and a follow-up question. The route
requires a verified user; the proposed fields are not persisted until the
user submits `POST /api/requests`.

### `POST /api/requests/normalize-photo` (verified)

Send `multipart/form-data` with `photo` (required, nonempty JPEG, PNG, or WebP)
and `text` (optional, at most 4000 characters). The declared MIME type must match
the image signature. The server reads at most `min(MAX_UPLOAD_BYTES, 5 MiB) + 1`
bytes and rejects a larger photo. For example:

```bash
curl -X POST http://127.0.0.1:5000/api/requests/normalize-photo \
  -H 'Authorization: Bearer sandbox:alice@unc.edu' \
  -F 'photo=@reference.png;type=image/png' \
  -F 'text=I want to borrow something like this.'
```

→ `200 {"normalized": NormalizedRequest, "fixture": false}`. A validated Gemini
proposal has `source: "gemini"`; provider or validation failure returns the
editable all-unknown `source: "manual"` result with the supplied text. The
response is a proposal only: the photo is not stored and no request or listing
is created or changed. Missing `photo` or text over 4000 characters returns
`400 validation_error` with `error.fields`; empty bytes return `400 invalid_image`;
unsupported MIME or signature returns `400 unsupported_image`; an oversized
photo returns `413 payload_too_large`. All errors use the shared API envelope.

For image-only input, `normalized.original_text` is `""` and `modes` is `null`.
Before `POST /api/requests`, the user must confirm or edit visual proposals,
enter a nonempty `original_text` and select at least one mode, then supply the
required request fields. Visual preferences affect ranking; they do not prove
required compatibility. Submit the confirmed `normalized` object plus top-level
`modes`, budget and deposit limits, dates, and area as appropriate. Matching
continues through `GET /api/requests/{id}/matches`.

### `GET /api/requests` (public)

→ `200 {"requests": [NeedRequest public view], "view": "public"}` — only
`visibility=public` and `status=open`. With `?mine=1` (verified) →
`{"requests": [owner view], "view": "owner"}`.

### `POST /api/requests` (verified)

Body: `original_text` (required), `normalized`, `modes` (required),
`budget_cents`, `max_deposit_cents`, `needed_by`, `use_start`, `use_end`,
`pickup_windows`, `area`; services may instead supply `service_duration_minutes`
and private `service_time_windows`. → `201 {"request": owner view, "view": "owner"}`.

### `GET /api/requests/{id}`

Requester → `{"request": owner view, "view": "owner"}`. Anyone else → the
public view only if published, else `404` (private requests are not revealed).

### `PATCH /api/requests/{id}` (requester only)

Partial fields as create; `"status": "cancelled"` to cancel. `409 request_closed` once closed.

### `GET /api/requests/{id}/matches` (requester only)

```json
{
  "request_id": "9b3f…",
  "source": "deterministic",
  "fixture": false,
  "confirmed": [],
  "needs_confirmation": [{
    "listing_id": "4a0c…",
    "mode": "borrow",
    "score": 1.0006662225183212,
    "reasons": [
      "Listing supports requested mode: borrow.",
      "Category matches: formalwear.",
      "Required type matches: suit.",
      "Required jacket_size matches: 40R.",
      "Preferred color matches: navy.",
      "Rental fee: 1500 cents, within budget 4000 cents.",
      "Proposed deposit: 20000 cents (100% of 20000 cents item value), separate from rental fee.",
      "Listing availability covers the requested dates."
    ],
    "shortcomings": [
      "deposit negotiation required: proposed deposit 20000 cents exceeds maximum 8000 cents."
    ],
    "unknown_required": ["deposit_agreement"],
    "listing": {
      "id": "4a0c…",
      "owner_id": "0f1c…",
      "owner": {"id": "0f1c…", "display_name": "Member 0f1c6b", "confirmed_email_domain": "unc.edu", "verification_source": "sandbox", "badge": "Sandbox identity (not verified)", "is_demo": true},
      "title": "Navy suit 40R",
      "category": "formalwear",
      "description": "Two-piece, worn twice.",
      "specifications": {"type": "suit", "jacket_size": "40R", "color": "navy"},
      "condition": "good",
      "accessories": ["garment bag"],
      "known_defects": [],
      "allowed_modes": ["borrow", "sale"],
      "sale_price_cents": 9000,
      "rental_fee_cents": 1500,
      "proposed_item_value_cents": 20000,
      "collateral_percent": 100,
      "availability": {"available_from": "2026-10-12T12:00:00Z", "available_until": "2026-10-16T22:00:00Z", "notes": "Most weekdays after 2pm for pickup"},
      "meeting_spot_ids": ["7d2e…"],
      "status": "available",
      "active_exchange_id": null,
      "public_photo_url": "/media/public/ab/ab12….png",
      "created_at": "2026-10-10T19:01:00Z",
      "updated_at": "2026-10-10T19:01:00Z"
    }
  }],
  "rejected": []
}
```

Every entry includes the full current `listing`; the route drops any id that
is not a real available listing. Candidates exclude the requester's own listings.
Matching uses the request's confirmed owner-view fields and the real catalog
rows; known incompatibilities appear in `rejected`, while unknown required
values and unaffordable proposed collateral appear in `needs_confirmation`.
The example listing covers the requested dates. It remains in
`needs_confirmation` solely because its proposed $200 deposit exceeds the
requester's $80 maximum; the lender and borrower must negotiate an agreement.
For the second demo request, keep every field above the same except
`max_deposit_cents: 20000`. The navy suit moves to `confirmed`, with
`unknown_required: []` and no deposit shortcoming. The charcoal 46L suit is
rejected in both cases.

### `POST /api/requests/{id}/publish` (requester only)

→ `200 {"request": owner view, "public_preview": public view, "view": "owner"}`.

## Exchange endpoints

Every endpoint requires a verified user. Detail, messages, offers, evidence,
acceptance, and state changes require the listing owner or requester; outsiders
receive `403`. Exchange responses use `Cache-Control: private, no-store` and
`X-Content-Type-Options: nosniff`.

| Method | Path | Body | Implemented result |
|---|---|---|---|
| GET | `/api/exchanges` | — | `200 {"exchanges": [Exchange with listing summary]}` for all caller-owned or requested sale, borrow, and service exchanges; no mode parameter is needed |
| POST | `/api/exchanges` | `{"listing_id":"…","mode":"sale"|"borrow"|"service","source_request_id":"…"?}` | `201 {"exchange": Exchange,"current_offer": OfferRevision}` for items; service starts with `current_offer: null` |
| GET | `/api/exchanges/{id}` | — | Item: `exchange`, `current_offer`, `offers`, `simulation_notice`, `deposit_status`, `participants`, `confirmations`, `max_upload_bytes`; service: `fixture: false`, `exchange`, `current_offer`, `offers`, `listing`, `participants` |
| GET | `/api/exchanges/{id}/messages` | item: `?after=<iso>` optional | `200 {"messages":[Message]}` for items; service also includes `fixture:false` |
| POST | `/api/exchanges/{id}/messages` | `{"body":"…"}` | `201 {"message":Message}` |
| POST | `/api/exchanges/{id}/offers` | Item offer terms or service price, duration, scheduled UTC time | `201 {"offer":OfferRevision,"exchange":Exchange}`; changed terms clear both acceptances; unchanged item/service terms return the existing revision with `200` |
| POST | `/api/exchanges/{id}/accept` | `{"version":2,"lower_deposit_acknowledged":true?}` | `200 {"exchange":Exchange,"current_offer":OfferRevision}`; stale version `409 stale_offer`; competing reservation `409 reservation_conflict` |
| POST | `/api/exchanges/{id}/complete` | Service only: `{"confirm":true}` | `200 {"exchange":Exchange}`; both independent confirmations complete a scheduled service; items get `409 invalid_transition` |
| GET | `/api/exchanges/{id}/evidence` | — | Item: `200 {"evidence":[Evidence]}`; service: `409 invalid_transition` |
| POST | `/api/exchanges/{id}/evidence` | Item only: multipart `photo` and `stage` | `201 {"evidence":Evidence}`; service: `409 invalid_transition` |
| GET | `/api/exchanges/{id}/evidence/{evidence_id}` | Item only: `?preview=1` optional | Private image bytes, or authenticated JSON `{"data_url":"data:image/jpeg;base64,..."}` preview; service: `409 invalid_transition` |
| POST | `/api/exchanges/{id}/handoff` | Item only: `{"confirm":true,"accept_condition":true}` | After pickup evidence and both confirmations: sale → `completed`, borrow → `on_loan`; service: `409 invalid_transition` |
| POST | `/api/exchanges/{id}/return` | Borrow only: `{"action":"initiate"|"accept"|"issue","reason":"…"?}` | Borrower before-return and owner after-return evidence precede mutual completion; issue → `disputed`; sale/service: `409 invalid_transition` |
| POST | `/api/exchanges/{id}/cancel` | Service: `{"reason":"…"}` | Service `negotiating` or `scheduled` → `cancelled`; items may cancel while negotiating/reserved before either pickup confirmation |
| POST | `/api/exchanges/{id}/dispute` | Service: `{"reason":"…"}` | Service `scheduled` or `completed` → `disputed`; borrow items may dispute in return_pending with a specific reason |
| POST | `/api/exchanges/{id}/review` | `stars`, five `structured_answers`, optional `comment` | Completed item exchange only, participant only; one review per participant, `201 {"review":Review}` |

If `source_request_id` is supplied, it must identify the caller's request,
have status `draft` or `open`, and include the selected exchange mode. Missing
or foreign item requests return `404`; closed requests return `409 request_closed`;
a mode mismatch returns `400 validation_error`. Service creation rejects a
missing, foreign, or nonservice source with `400 validation_error`, and a closed
service source with `409 request_closed`. An exchange cannot be started for the
caller's own listing or for an unavailable listing.

Item offers record sale price or rental fee, agreed item value and deposit,
condition snapshot, and required pickup/return meeting terms. Both participants
accept the current revision before `reserved`. A lender must explicitly
acknowledge the uncovered value of a lower deposit. Service offers instead
record `service_price_cents`, `service_duration_minutes`, and
`service_scheduled_at` within an available window. Both participants accept
that revision before `scheduled`; item deposit, collateral, condition, meeting,
evidence, handoff, pickup, and return fields are rejected for services.

Deposit status values are simulated and labeled:
`{"state": "simulated_pending"|"simulated_held"|"simulated_released", "label": "Simulated: no real funds are reserved or charged."}`.
Item detail includes `confirmations` with `stage`
(`handoff` or `return`), `participant_id`, `condition_acknowledged_at`,
`confirmed_at`, and `evidence_ids`. `max_upload_bytes` is the server's evidence
upload limit. Evidence previews remain private and must use the authenticated
API request; no public URL or storage path is returned.

### Exchange status rules (enforced in Python)

- `negotiating → reserved` only after both accept the latest offer and
  `reserve_listing()` succeeds in the same transaction.
- `reserved → completed` (sale) after required evidence and both handoff confirmations; `mark_listing_sold()`.
- `reserved → on_loan` (borrow) after equivalent pickup confirmation.
- `on_loan → return_pending` when return is initiated.
- `return_pending → completed` after before/after evidence and mutual confirmation; `release_listing()`.
- `return_pending → disputed` on a raised issue; never an automatic charge.
- Service: `negotiating → scheduled` after both accept the latest service offer;
  `scheduled → completed` after both confirm the session happened. Services
  cannot enter `reserved`, `on_loan`, or `return_pending`.
- Service `cancelled` from `negotiating` or `scheduled` records a reason and
  releases an active reservation. Service `disputed` from `scheduled` or
  `completed` records a reason and never charges funds. Item cancellation and
  the general dispute endpoint remain follow-up work.
- Any change to price, collateral, meeting, condition, or dates creates a new revision and resets both acceptances.
- Duplicate actions are rejected (`409`) or idempotent.

## Person 2 function signatures (`server/intelligence/`)

```python
def normalize_request(text: str, now: datetime, timezone: str) -> dict:
    """NormalizedRequest (above). Gemini structured output validated by Pydantic.
    Unknown → null. Ambiguous dates → ambiguous_dates + follow_up_questions.
    On Gemini failure/timeout: source="manual", all null, a follow-up question
    explaining the user must fill the form. Never fabricate values."""

def match_listings(request: dict, listings: list[dict]) -> dict:
    """request = NeedRequest owner view; listings = current available Listing dicts.
    Returns {"source": "deterministic", "confirmed": [MatchEntry],
             "needs_confirmation": [MatchEntry], "rejected": [MatchEntry]}.
    MatchEntry = {"listing_id", "mode": "sale"|"borrow"|"service"|None, "score": float|None,
                  "reasons": [str], "shortcomings": [str], "unknown_required": [str]}.
    Hard checks (mode, known required specs, dates, budget, deposit affordability
    for loans, service duration/windows, availability) are deterministic. Unknown required attribute → needs_confirmation,
    never confirmed. Every listing_id must come from `listings`."""

def evaluate_price(price_cents: int, reference: dict | None) -> dict:
    """{"verdict": "allow"|"warn"|"block"|"insufficient_data", "reason": str,
        "reference_version": int|None, "stub": bool}.
    block if price > upper; block if 2*price <= lower; warn if lower/2 < price < lower;
    allow if lower <= price <= upper. Rental 0 cents = explicit free loan, allowed.
    reference None → insufficient_data (advisory only)."""
```

## Shared helpers (Person 1 → Persons 3 and 4)

- `server.auth.require_verified_user`, `optional_user`, `current_profile()`.
- `server.reservation.reserve_listing(session, listing_id, exchange_id) -> bool`,
  `release_listing(...)`, `mark_listing_sold(...)`. Single conditional UPDATE each;
  caller commits.
- `server.storage.get_storage().save(scope, stream, max_bytes) -> StoredFile`,
  `.send(scope, path, content_type)`, `.delete(scope, path)`;
  `authorize_private_read(viewer_id, participant_ids)`. `scope` is `public` for
  listing photos and `private` for evidence; Supabase uses distinct buckets.
  Call `authorize_private_read` after loading the evidence's exchange and its
  participants, then `send("private", ...)` in the same Flask request. The
  adapter refuses private `send` without that check and never returns a signed
  evidence URL. The exchange route must still verify the requested evidence
  belongs to the authorized exchange.
- `server.validation.json_body()`, `FieldErrors`, `money_cents`, `percent`,
  `string`, `choice_list`, `datetime_utc`, `json_object`.
- `server.errors.ApiError(status, code, message, fields)`.
- Browser: `window.api.get/post/patch/upload`, `api.getToken/setToken`,
  `api.sessionToken()`, `api.formatCents`, `api.formatTime`; errors are
  `api.ApiError {status, code, fields}`. API calls await the current Supabase
  session on every page; `getToken()` is only a synchronous snapshot.

## Completion branch contracts

### Listing publication and required fields

New listings are private `draft` records, invisible to other users and matching.
Existing inventory is grandfathered without changing records, IDs or photos.
`POST /api/listings` returns `201 {"listing":Listing}` with `status:"draft"`.
A draft's detail and `status=all` owner collection require the owner's token;
private draft responses are `private, no-store` with `nosniff`.

| Kind | Required to publish | Optional |
|---|---|---|
| Sale | Title, category, description, sale price in integer cents, image | Unknown condition, specifications, accessories/defects, meeting preferences |
| Borrow | Title, category, description, proposed item value in cents, image | Fee defaults explicitly to 0; collateral defaults to 100%; condition/specifications, accessories/defects, availability and meeting preferences |
| Sale + borrow | Both sets of monetary requirements, title, category, description, image | Same item optional fields |
| Service | Title, description, one of the eight service categories defined above, service price in cents, duration 1–1440 minutes, nonempty availability windows with one fitting the duration, image | No physical-item fields |

Unknown condition/specifications remain unknown. Zero prices are valid.

1. Create a validated draft with the existing JSON shape.
2. `POST /api/listings/{id}/publish`, owner only, multipart `photo`.
   All persisted terms are revalidated. The server reads at most
   `min(MAX_UPLOAD_BYTES,5 MiB)+1` bytes and decodes actual JPEG/PNG/WebP
   content (still images, maximum 16 megapixels). Only then is the image stored
   and the listing made available. Success: `200 {"listing":Listing}`.
3. Retrying publication of the same successfully published draft returns that
   listing. Failed image validation leaves the draft private; commit failure
   deletes the newly stored file. Partial local writes are removed; uncertain
   remote upload results trigger deletion of that generated path. Storage
   outages can prevent cleanup (maintenance required); the listing stays private.
   The form keeps its values and draft ID. My Listings → Finish publishing restores
   saved fields at `/listings/new?draft={id}`; a file must be selected again after navigation.

`PATCH` cannot publish a draft or relist a new record without an image.
`POST /photo` is for replacement on editable published listings; drafts use
`/publish`. Both field edits and photo replacement take a listing lock and
reject `reserved`/`sold` with `409 listing_locked`, preserving agreed records.
An available/withdrawn listing may replace its image; the previous file is
removed after successful commit. Existing sample listings remain supported.

Creation endpoints (`/api/listings`, `/api/requests`, `/api/exchanges`, and
exchange `/messages`) accept an optional `Idempotency-Key` of 8–80 letters,
digits, hyphens or underscores. Keys belong to the authenticated creator.
Identical retries return the same record; changed payloads with the same key
return `409 idempotency_conflict`. Clients retain the key after a failed/lost
response and generate a new one for a new action. Keys are not public fields.
Mode filtering occurs before the 200-record limit in catalog and matching.

### Account and private meeting context

`PATCH /api/me` accepts either/both `display_name` (nonempty, maximum 80) and
`preferred_meeting_spot_id` (active catalog ID or null). The preference appears
in the caller's `/api/me`, never the public profile. It is shared as a preference
with exchange participants, without identifying a home/current location.

`GET /api/meeting-spots` retains IDs, labels, areas and recorded notes, adding
nullable coordinates, coordinate provenance, and `safety_attributes` keys
`lighting`, `cameras`, `staffing`, `public_access`, `opening_hours`; unverified
values are null. `safety_source` and `safety_checked_at` are nullable. Recorded
seed notes are explicitly distinguished from independently checked attributes.
UNC map reference coordinates are documented in `server/meeting_sources.py`;
Union/Davis points identify buildings, not verified entrance positions.
No source establishes camera coverage or live crowds. No safety scores exist.

Participant-only endpoints, `private, no-store` and `nosniff`:

- `GET /api/exchanges/{id}/locations` returns `locations`, every active
  `meeting_spots`, and `ranking:"unranked"|"straight_line_estimate"`.
- `PUT /api/exchanges/{id}/locations/me` accepts `{"landmark":"Near Davis"}`
  and optional numeric `latitude`/`longitude` within the campus bounds
  35.89–35.93, −79.08–−79.02. Coordinates are rounded to four decimals.
  Each participant can change only their own record; supplying `participant_id`
  is rejected. Response: `200 {"location":...}`.
- `DELETE /api/exchanges/{id}/locations/me` clears only the caller's record.

Locations expire in 24 hours, disappear from reads on expiry, and are deleted
when the exchange completes/cancels/disputes. Schedule
`flask --app server.app purge-exchange-locations` hourly for physical deletion
of expired records. Manual landmarks work without coordinates; no routing is
invented. With both positions supplied, catalog spots rank by maximum then
combined straight-line distance. Distances are estimates, never walking times.
The map and keyboard list propose the same spots; selecting does not accept.

Item offers still require agreed active pickup/return catalog spots as appropriate.
Services add independent offer fields `service_delivery:"remote"|"in_person"`
(default remote for existing contracts) and `service_meeting_spot_id`.
Example in-person offer:

```json
{"service_price_cents":2500,"service_duration_minutes":60,"service_scheduled_at":"2030-10-12T12:00:00Z","service_delivery":"in_person","service_meeting_spot_id":"7d2e0000000000000000000000000001"}
```

In-person services require an active spot at offer creation and acceptance;
remote services reject a meeting spot. New revisions reset both acceptances,
including location changes. Resubmitting identical service terms returns the same
revision with acceptances intact and creates no duplicate notification. Both accept the current revision before scheduling;
both confirm completion separately. Services still reject all item evidence,
pickup, handoff, collateral and return fields/transitions. Single active service
reservation capacity remains unchanged. No calendar capacity redesign.

### Persistent notifications

Verified-user routes, recipient scoped, `private, no-store` and `nosniff`:

- `GET /api/notifications` → `{"notifications":[{"id":"…","kind":"message","exchange_id":"…","url":"/exchanges/…","created_at":"…","read_at":null}],"unread_count":1}`.
  Latest 100 notifications; unread count includes older unread records.
- `POST /api/notifications/{id}/read` → `{"notification":...}`; foreign IDs 404.
- `POST /api/notifications/read-all` → `{"ok":true}`; caller only.

Events cover creation, messages, offer revisions/acceptances, reservation or
scheduling, condition evidence/confirmations, loan/return/service completion,
cancellation and disputes. Events commit in the domain transaction, roll back
on failure, exclude the actor, and deduplicate by recipient/event identity.
Message notifications contain no message text. Existing exchanges are not
backfilled with fabricated history. The UI polls every 20 seconds while visible.

Ambiguous interpreted dates stop the homepage before request creation. The user
reviews/edits the proposed dates and explicitly acknowledges them; editing a date
invalidates that acknowledgement. Visual photo proposals still require Accept or
Dismiss. Confirmed request creation retains its retry key after a lost response.
Server validation failures return to editable review rather than silently clearing
terms or changing the selected mode.

## Community clubs and profiles (c706community)

Clubs are seeded, fictional demo communities. There are no club create/delete,
role-changing or membership-removal endpoints. Membership is not verification,
insurance, a payment guarantee or a safety guarantee. Codes use Werkzeug scrypt
password hashes and are never included in responses or server logs.

### Club and membership shapes

```json
{"id":"club-id","slug":"demo-study-circle","name":"Study Circle (fictional DEMO club)","is_demo":true}
```

```json
{"club":{"id":"club-id","slug":"demo-study-circle","name":"Study Circle (fictional DEMO club)","is_demo":true},"role":"member"}
```

Roles are exactly `member` and `manager`. Public embedded profiles now also
include `avatar_url`, `bio`, `graduation_year` and `clubs: [Membership]`.
`GET /api/me` additionally includes private `preferred_meeting_spot_id`,
`show_transaction_history` and `created_at`. No auth subject or email is exposed.

| Endpoint | Request | Response |
|---|---|---|
| GET `/api/clubs/me` | verified bearer | `200 {"memberships":[Membership]}` |
| POST `/api/clubs/join` | verified; `{"code":"fictional team code"}` | `200 {"membership":Membership}`; repeated join keeps role and creates no duplicate |
| GET `/api/clubs/{club_id}` | current member | `200 {"club":Club}` |
| GET `/api/clubs/{club_id}/exchanges` | current manager | `200 {"exchanges":[ManagerExchange]}` |
| POST `/api/clubs/{club_id}/exchanges/{id}/review` | nonparticipant manager; body below | `200 {"exchange":ManagerExchange}` |

Invalid, empty or malformed join codes have the same generic result:

```json
{"error":{"code":"invalid_club_code","message":"Unable to join with that code","fields":{}}}
```

Nonmembers receive `404` club/listing/exchange errors. Members without the
manager role and managers reviewing their own exchanges receive `403 forbidden`.
Authentication remains the existing `401`/`403` contract.

### Club listing audience

Both item and service listing create bodies may add:

```json
{"audience":"club","club_id":"club-id"}
```

Omitting these fields preserves `audience:"public", club_id:null`. Responses
include `audience`, `club_id`, and sanitized `club: Club|null`. A public audience
requires null club ID; club audience requires a current membership. These fields
are immutable after creation. Invalid combinations give `400 validation_error`
with `audience` or `club_id` fields. The draft/photo publication flow is unchanged.

Collections, details, recommendations and match candidates enforce membership
before serialization and before deterministic matching. Inaccessible IDs return
`404`, including owner edits after membership loss. Drafts remain owner-only,
even to fellow members. Club photos use **private storage**, not the public
bucket. Their `/media/public/{path}` URLs enforce club membership and return 404
for anonymous/nonmember access; `?preview=1` returns authenticated
`{"data_url":"data:image/jpeg;base64,..."}` for browser images. Do not put a
bearer token in an image URL. The shared client fetches the preview with its API
helper and clears it when authorization changes.

### Club review gate

Exchange responses add `club: Club|null`, `club_review_state`,
`club_review_note: string|null`. Club exchanges snapshot their club association;
both participants must remain members. Review states are `not_required` (public),
`awaiting_participants`, `pending`, `approved`, `changes_requested`.

After both latest-revision acceptances, a club exchange stays `negotiating` with
`pending` review. No reservation or scheduling occurs yet. New changed offers
reset both acceptances and the review; identical offer retries keep their state.
Requesting changes requires a nonempty note of at most 300 characters and a new
offer before accepting again. Public acceptances retain their existing behavior.

Review body includes the displayed version to prevent stale manager approval:

```json
{"decision":"approve","version":2,"note":null}
```

```json
{"decision":"request_changes","version":2,"note":"Please clarify the agreed schedule."}
```

`version` is a required positive integer. Unknown decision, missing version or
invalid note gives `400 validation_error`. Old version gives `409 stale_offer`;
missing acceptances or nonpending review gives `409 review_not_ready`. Duplicate
approval of the same approved revision is idempotent. Under the exchange row
lock, approval rechecks participant memberships, terms, lender acknowledgment,
service availability and active service meeting spot, then uses the existing
atomic `reserve_listing` protection. Items become `reserved`, services become
`scheduled`. A losing reservation gives `409 reservation_conflict` and rolls back
review changes. Existing cancellation/dispute/payment simulation behavior stays.

`ManagerExchange` is an explicit allowlist, never an ordinary exchange detail:

```json
{"id":"exchange-id","listing_title":"Demo suit","participants":{"owner":"Alice (demo)","requester":"Bob (demo)"},"mode":"borrow","status":"negotiating","club_review_state":"pending","club_review_note":null,"offer_version":2,"agreed_terms":{"sale_price_cents":null,"rental_fee_cents":1500,"agreed_item_value_cents":20000,"deposit_cents":20000,"lower_deposit_acknowledged":false,"pickup_at":"2026-10-13T18:00:00Z","return_deadline":"2026-10-15T22:00:00Z"}}
```

Service agreed terms instead contain only `service_price_cents`,
`service_duration_minutes`, `service_scheduled_at`. Managers never get messages,
evidence, meeting-spot IDs, private locations/contact data, condition free text,
request IDs/text or counterpart profile objects through these endpoints.
Ordinary private exchange endpoints remain participant-only, including locations.

### Public community profiles

`GET /api/profiles/{profile_id}` is public (`404` for missing profile):

```json
{"profile":{"id":"profile-id","display_name":"Alice (demo)","confirmed_email_domain":"unc.edu","verification_source":"sandbox","badge":"Sandbox identity (not verified)","is_demo":true,"avatar_url":null,"bio":null,"graduation_year":null,"clubs":[],"rating":{"average":null,"review_count":0},"completed_counts":{"bought":0,"sold_lent_provided":0,"borrowed":0,"services":0},"transaction_history":null}}
```

Counts derive only from completed exchanges. `sold_lent_provided` counts the
owner role in sale/borrow/service; `bought` and `borrowed` count requester roles;
`services` counts service participation in either role (overlaps provided count).
Ratings aggregate reviews attached to currently completed exchanges. Empty
averages stay null. No demo ratings or completed exchanges are seeded.

PATCH `/api/me` accepts existing fields plus:

```json
{"bio":"I share study supplies.","graduation_year":2028,"show_transaction_history":true}
```

Bio is null or at most 300 characters; year is null or integer 1900–2200;
history visibility must be a boolean, defaults false. Response is
`200 {"profile": MeProfile}`; invalid values produce `400 validation_error` with
per-field messages. Preferred meeting spot stays private.

Only explicit opt-in changes `transaction_history` from null to an array:

```json
[{"listing_title":"Demo lamp","mode":"sale","role":"requester","completed_at":"2026-10-11T18:00:00Z"}]
```

No transaction IDs, counterparty, money, deposit, locations, messages, evidence,
request text or noncompleted exchanges appear. Club-restricted titles are omitted
even after opt-in. Completion date derives from the existing exchange's updated
UTC timestamp; no new history or completion-date model is introduced.

### Avatar replacement

POST `/api/me/avatar`, authenticated multipart `photo`, returns
`200 {"profile": MeProfile}`. Accepts still JPEG, PNG, WebP with matching MIME,
limit `min(MAX_UPLOAD_BYTES, 1 MiB)`. Reuses the decoded-image checks (16 megapixels,
no animation, complete image), EXIF orientation, then resizes to at most 512×512
and writes metadata-free RGB WebP through public storage. Unsupported/truncated
images give `400 unsupported_image`, MIME mismatch `400 validation_error`, size
`413 payload_too_large`, unavailable decoder/storage `503`. Prior avatar is
removed only after successful commit; a failed commit cleans the new file.
Profile reads use private/no-store caching to reflect visibility changes promptly.
