# Campus Current API contracts (M1–M2)

All implemented API endpoints return JSON. IDs are strings, money is integer USD cents, and timestamps are UTC ISO 8601. An unknown `/api` route returns:

```json
{"error":{"code":"not_found","message":"API route not found.","fields":{}}}
```

## Health

`GET /api/health` returns HTTP 200:

```json
{"status":"ok"}
```

This establishes HTTP availability only.

## Public listings

`GET /api/listings?page=1&per_page=20` returns HTTP 200. `page` defaults to 1 and permits 1–10000. `per_page` defaults to 20 and permits 1–50. Listings are ordered by creation time, newest first, then ID ascending. Only `active` listings are returned.

```json
{
  "items": [
    {
      "id": "8f8468e5-7e98-4844-865f-77f309c1ff10",
      "title": "DEMO: Interview suit",
      "category": "Clothing",
      "description": "Fictional inventory for local development only.",
      "specifications": {"size": "medium", "color": "navy"},
      "condition": "Good; fictional demo item.",
      "accessories": ["jacket", "trousers"],
      "modes": ["borrow"],
      "sale_price_cents": null,
      "rental_fee_cents": 1500,
      "proposed_item_value_cents": 20000,
      "collateral_percent": 100,
      "public_photo_path": null,
      "owner_display_name": "DEMO: Campus Current lender",
      "is_demo": true,
      "created_at": "2026-10-10T17:00:00Z"
    }
  ],
  "page": 1,
  "per_page": 20,
  "total": 1
}
```

The sample ID and timestamp illustrate the response shape; actual IDs and timestamps come from the server. Unknown optional values are `null`. `modes` is `["sale"]`, `["borrow"]`, or `["sale","borrow"]`. `total` counts active listings before pagination.

`GET /api/listings/<id>` returns HTTP 200 with one object in the same public shape. A missing or nonactive listing returns HTTP 404 with the standard `not_found` error. Invalid pagination returns HTTP 400 with `invalid_input` and field errors. Missing or unreachable database returns HTTP 503 with `database_unavailable`.

Public serializers never include Profile IDs, confirmed email domain, email addresses, or private exchange data. A displayed name is public; it does not imply identity verification or trustworthiness. Exact schedules are absent from this M2 response.

## Persistence boundary

`Profile.id` is reserved for the authenticated provider user ID in M3. The development seed uses a visibly marked fictional ID. `Listing.id` is a server-generated string UUID for normal records. The schema stores sale price, rental fee, proposed item value, and collateral percentage separately. Values are nullable when unknown or inapplicable; M3 will add write validation before accepting user input.

M2 implements reads only. Person 2's future Python interfaces remain `normalize_request(text, now, timezone)`, `match_listings(request, listings)`, and `evaluate_price(price, reference)`. Their exact input/output schemas and Person 4's exchange models and reservation interface still need team agreement before integration.
