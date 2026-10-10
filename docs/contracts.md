# API contracts (frozen scaffold v1)

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
  "specifications": {"jacket_size": "40R", "color": "navy"},
  "condition": "good",
  "accessories": ["garment bag"],
  "known_defects": [],
  "allowed_modes": ["borrow", "sale"],
  "sale_price_cents": 9000,
  "rental_fee_cents": 1500,
  "proposed_item_value_cents": 20000,
  "collateral_percent": 100,
  "availability": {"available_from": null, "available_until": null, "notes": "weekday afternoons"},
  "meeting_spot_ids": ["7d2e…"],
  "status": "available",
  "active_exchange_id": null,
  "public_photo_url": "/media/public/ab/ab12….png",
  "created_at": "2026-10-10T19:01:00Z",
  "updated_at": "2026-10-10T19:01:00Z"
}
```

- `allowed_modes`: subset of `["sale", "borrow"]`, non-empty.
- `condition`: one of `new`, `like_new`, `good`, `fair`, `worn`, or null.
- `status`: `available` | `reserved` | `sold` | `withdrawn`. Only the reservation
  helper moves a listing to `reserved`/`sold`; owners may set `available`/`withdrawn`.
- `"sale"` requires `sale_price_cents`; `"borrow"` requires
  `proposed_item_value_cents`. For borrow, a missing `rental_fee_cents` becomes
  `0` (explicit free loan) and a missing `collateral_percent` becomes `100`.
- `collateral_percent` is the owner's proposal (0-100). The deposit in cents is
  decided per offer revision, not here.

### NeedRequest (owner view)

```json
{
  "id": "9b3f…",
  "requester_id": "0f1c…",
  "original_text": "I need a navy suit, 40R, for an interview next Tuesday. Would rather borrow.",
  "normalized": {"source": "manual", "category": "formalwear", "required_specifications": {"jacket_size": "40R"}, "preferred_specifications": {"color": "navy"}, "follow_up_questions": []},
  "modes": ["borrow", "sale"],
  "budget_cents": 4000,
  "max_deposit_cents": 8000,
  "needed_by": "2026-10-14T13:00:00Z",
  "use_start": "2026-10-13T16:00:00Z",
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

### NeedRequest (sanitized public view)

No `original_text`, no `pickup_windows`, no `use_start`/`use_end`, no precise
`needed_by` time, no requester contact.

```json
{
  "id": "9b3f…",
  "requester": {"id": "0f1c…", "display_name": "Member 0f1c6b", "confirmed_email_domain": "unc.edu", "verification_source": "sandbox", "badge": "Sandbox identity (not verified)", "is_demo": true},
  "category": "formalwear",
  "modes": ["borrow", "sale"],
  "required_specifications": {"jacket_size": "40R"},
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
  "required_specifications": {"jacket_size": "40R"},
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

`source` is `gemini` | `manual` | `stub`. Unknown stays `null`. The user edits
this object before searching; the server stores whatever they confirm.

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

`status`: `negotiating` | `reserved` | `on_loan` | `return_pending` |
`completed` | `disputed` | `cancelled`.

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

Query: `status` (default `available`; `all` for every status), `category`,
`mode` (`sale`|`borrow`), `owner_id`. → `200 {"listings": [Listing]}`.

### `POST /api/listings` (verified)

Body: any Listing fields except `id`, `owner_id`, `owner`, `status`,
`active_exchange_id`, `public_photo_url`, timestamps. Required: `title`,
`category`, `allowed_modes`.

```json
{"title": "Navy suit 40R", "category": "formalwear", "allowed_modes": ["borrow", "sale"], "sale_price_cents": 9000, "rental_fee_cents": 1500, "proposed_item_value_cents": 20000, "collateral_percent": 100, "specifications": {"jacket_size": "40R"}, "condition": "good", "meeting_spot_ids": ["7d2e…"]}
```

→ `201 {"listing": Listing}`; `400 validation_error` with per-field messages.

### `GET /api/listings/{id}` (public) → `200 {"listing": Listing}` | `404`.

### `PATCH /api/listings/{id}` (owner only)

Same fields as create, partial; plus `"status": "available"|"withdrawn"`.
→ `200 {"listing": Listing}`; `403 forbidden` for a different user;
`409 listing_locked` while reserved/sold.

### `POST /api/listings/{id}/photo` (owner only)

Multipart field `photo` (JPEG/PNG/WebP by magic bytes, ≤ `MAX_UPLOAD_BYTES`).
→ `200 {"listing": Listing}`; `400 unsupported_image`; `413 payload_too_large`.

### `GET /media/public/{path}` (public) — listing photo bytes.

### `GET /api/meeting-spots` (public) → `200 {"meeting_spots": [MeetingSpot]}`.

### `POST /api/requests/normalize` (verified)

Body `{"text": "I need a navy suit…"}` →
`200 {"normalized": NormalizedRequest, "fixture": true|false}`.
Currently a stub (`source: "stub"`, everything null, one follow-up question).

### `GET /api/requests` (public)

→ `200 {"requests": [NeedRequest public view], "view": "public"}` — only
`visibility=public` and `status=open`. With `?mine=1` (verified) →
`{"requests": [owner view], "view": "owner"}`.

### `POST /api/requests` (verified)

Body: `original_text` (required), `normalized`, `modes` (required),
`budget_cents`, `max_deposit_cents`, `needed_by`, `use_start`, `use_end`,
`pickup_windows`, `area`. → `201 {"request": owner view, "view": "owner"}`.

### `GET /api/requests/{id}`

Requester → `{"request": owner view, "view": "owner"}`. Anyone else → the
public view only if published, else `404` (private requests are not revealed).

### `PATCH /api/requests/{id}` (requester only)

Partial fields as create; `"status": "cancelled"` to cancel. `409 request_closed` once closed.

### `GET /api/requests/{id}/matches` (requester only)

```json
{
  "request_id": "9b3f…",
  "source": "stub",
  "fixture": true,
  "confirmed": [],
  "needs_confirmation": [{"listing_id": "4a0c…", "mode": null, "score": null, "reasons": [], "shortcomings": ["Matching is not implemented yet (stub); compatibility has not been checked."], "unknown_required": [], "listing": Listing}],
  "rejected": []
}
```

Every entry includes the full current `listing`; the route drops any id that
is not a real available listing. Candidates exclude the requester's own listings.

### `POST /api/requests/{id}/publish` (requester only)

→ `200 {"request": owner view, "public_preview": public view, "view": "owner"}`.

## Person 4 endpoints (stubs now; contract to implement)

All require a verified user and, once implemented, a participant check
(`exchange.owner_id` or `exchange.requester_id == caller`), else `403`.

| Method | Path | Body (request) | Response now | Response when real |
|---|---|---|---|---|
| GET | `/api/exchanges` | — | `{"fixture": true, "exchanges": [Exchange]}` | `{"exchanges": [Exchange + listing summary]}` for the caller |
| POST | `/api/exchanges` | `{"listing_id", "mode", "source_request_id"?}` | `501` | `201 {"exchange": Exchange, "current_offer": OfferRevision}` |
| GET | `/api/exchanges/{id}` | — | `{"fixture": true, "simulation_notice", "exchange", "current_offer", "offers", "deposit_status", "participants"}` | same shape, real |
| GET | `/api/exchanges/{id}/messages` | `?after=<iso>` | `{"fixture": true, "messages": [Message]}` | `{"messages": [Message]}` |
| POST | `/api/exchanges/{id}/messages` | `{"body"}` | `501` | `201 {"message": Message}` |
| POST | `/api/exchanges/{id}/offers` | OfferRevision terms (no `version`) | `501` | `201 {"offer": OfferRevision, "exchange": Exchange}`; new version resets acceptances |
| POST | `/api/exchanges/{id}/accept` | `{"version": 2, "lower_deposit_acknowledged": true?}` | `501` | `200 {"exchange", "current_offer"}`; `409 stale_offer` if version ≠ current; `409 reservation_conflict` if the atomic reserve fails; repeat accept is idempotent |
| GET | `/api/exchanges/{id}/evidence` | — | `{"fixture": true, "evidence": [Evidence]}` | `{"evidence": [Evidence]}` |
| POST | `/api/exchanges/{id}/evidence` | multipart `photo`, field `stage` | `501` | `201 {"evidence": Evidence}` |
| GET | `/api/exchanges/{id}/evidence/{evidence_id}` | — | `501` | image bytes, participants only |
| POST | `/api/exchanges/{id}/handoff` | `{"confirm": true, "accept_condition": true}` | `501` | `200 {"exchange"}`; sale → `completed`, loan → `on_loan` after both confirm |
| POST | `/api/exchanges/{id}/return` | `{"action": "initiate"|"accept"|"issue", "reason"?}` | `501` | `200 {"exchange"}`; `on_loan → return_pending → completed`, or `disputed` |
| POST | `/api/exchanges/{id}/review` | Review fields | `501` | `201 {"review": Review}` |
| POST | `/api/exchanges/{id}/cancel` | `{"reason"}` | `501` | `200 {"exchange"}`; releases an unused reservation; cannot cancel `on_loan` |
| POST | `/api/exchanges/{id}/dispute` | `{"reason"}` | `501` | `200 {"exchange"}`; status `disputed`, no charge ever |

Deposit status values are simulated and labeled:
`{"state": "simulated_pending"|"simulated_held"|"simulated_released", "label": "Simulated: no real funds are reserved or charged."}`.

### Exchange status rules (enforced in Python)

- `negotiating → reserved` only after both accept the latest offer and
  `reserve_listing()` succeeds in the same transaction.
- `reserved → completed` (sale) after required evidence and both handoff confirmations; `mark_listing_sold()`.
- `reserved → on_loan` (borrow) after equivalent pickup confirmation.
- `on_loan → return_pending` when return is initiated.
- `return_pending → completed` after before/after evidence and mutual confirmation; `release_listing()`.
- `return_pending → disputed` on a raised issue; never an automatic charge.
- `cancelled` from `negotiating`/`reserved` only; `release_listing()`; records a reason.
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
    MatchEntry = {"listing_id", "mode": "sale"|"borrow"|None, "score": float|None,
                  "reasons": [str], "shortcomings": [str], "unknown_required": [str]}.
    Hard checks (mode, known required specs, dates, budget, deposit affordability,
    availability) are deterministic. Unknown required attribute → needs_confirmation,
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
  `authorize_private_read(viewer_id, participant_ids)`.
- `server.validation.json_body()`, `FieldErrors`, `money_cents`, `percent`,
  `string`, `choice_list`, `datetime_utc`, `json_object`.
- `server.errors.ApiError(status, code, message, fields)`.
- Browser: `window.api.get/post/patch/upload`, `api.getToken/setToken`,
  `api.formatCents`, `api.formatTime`; errors are `api.ApiError {status, code, fields}`.
