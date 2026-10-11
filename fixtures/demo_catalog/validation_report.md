# Demo catalog validation

Status: passed. These are proposed fictional demo fixtures, not created marketplace inventory. No existing database was seeded or altered; no image was downloaded, acquired, or committed.

## Observed inventory

| File | Listings | Demo owner definitions |
| --- | ---: | ---: |
| clothing_events.json | 11 | 3 |
| electronics_academics.json | 11 | 3 |
| dorm_outdoors.json | 11 | 3 |
| services.json | 9 | 3 |
| Total | 42 | 12 |

11 borrow-only, 11 sale-only, 11 sale-and-borrow, and 9 services. Four listings offer explicit zero-cent sales (“Free to keep”); eight offer explicit zero-cent borrowing fees. Free-loan deposits remain separate owner proposals. Null prices are never labeled free.

## Checks and execution

Executed successfully:

```sh
.venv/bin/python fixtures/demo_catalog/validate_catalog.py > /tmp/catalog_validation_results.json
```

The reusable validator checked envelope and editable API field whitelists; unique stable listing/owner keys; local owner references; visible demo titles, descriptions, and owner labels; category/mode separation; allowed conditions; integer-cent money; null unused price/value/collateral fields; percentage bounds; UTC Z timestamps and ordered intervals; each service window's Oct 11 America/New_York relevance; a window sufficient for offered duration; unique titles and descriptions; and all 42 image-manifest entries. Metadata remains outside API bodies. Services contain exactly the seven editable fields documented in the service POST example and contain no item fields.

It exercised the existing `server.routes.catalog._apply_listing_fields` validator for all **42** fixture bodies and persisted test rows only in a temporary SQLite database. It used `db.create_all()` for this shape/validator check; this is not a migration test, an authenticated API test, or a production/development seed operation. No Gemini call was made. All temporary data and storage directories were removed when the check ended.

Automated prohibited-claim/contact checks were supplemented by a review of all listing descriptions/specifications. No fabricated review scores, completed exchanges, verification, popularity, environmental impact, student identity, contact information, or institutional/club affiliation was found. Manufacturer/model identifiers describe objects only. The retired helmet is explicitly display-only with protective fitness unknown; the multimeter makes no safety-rating/calibration/mains-use claim; sleeping-bag temperature suitability remains unknown.

Correction made: clothing-navy-suit-40r now lists the described “small crease at the trouser hem” in `known_defects` rather than leaving the structured list empty. No shared source file was edited.

## Deterministic matching observations

Requests were manually specified fixture checks, not Gemini outputs. Every match references one of the 42 supplied listing keys.

Suit request: borrow, formalwear, required type=suit and jacket_size=40R; preferred navy; rental budget 2000 cents; max deposit 8000 cents; October 11, 14:00–22:00 UTC.

- Confirmed **1**: clothing-navy-suit-40r; matching type/size/color, 1500-cent fee, separate 5400-cent deposit proposal (30% of 18000 cents), known availability covers dates.
- Needs confirmation **1**: clothing-black-suit-size-unknown; unknown jacket size and dates; 10500-cent deposit proposal exceeds 8000-cent maximum (“deposit negotiation required”).
- Rejected **40**: known category, size, mode, and/or budget incompatibilities. The gray 38S suit also has a 2500-cent rental fee above the budget; the charcoal 44L has an incompatible jacket size.

Service request: proofreading, 45 minutes, budget 2000 cents, October 11 7–9 PM America/New_York (23:00 UTC through October 12 01:00 UTC).

- Confirmed **1**: demo-evening-essay-proofreading, 1500 cents, offered 45 minutes and a full two-hour compatible window.
- Needs confirmation **0** for this fully specified request.
- Rejected **41**: demo-extended-proofreading costs 2500 cents; demo-late-proofreading has only 30 minutes of feasible overlap despite a 60-minute offered duration; tutoring/moving help fail category; all physical items fail service/item mode separation.

## Integration limits and image handoff

- No fixture has been loaded into the existing demo database. Existing seed records remain preserved. Idempotent loading and sandbox/is_demo profile enforcement require Evan's reviewed seed integration; fixture wrapper owner definitions do not impersonate authenticated users or claim verification.
- The current service API cannot store `specifications`. Subject/scope is described naturally; deterministic matching cannot certify a required structured subject/document constraint from prose. Such requirements must remain needs-confirmation until Evan defines shared storage/contract support. No unsupported service field was invented.
- All 42 image entries are **planned_original_photo** with null source URL, unique filenames, and **pending permission/attribution review**. No rights are claimed as acquired. Image sourcing/loading remains deferred.
- Storage currently accepts magic-byte-identified JPEG/PNG/WebP up to the configured maximum and creates server-generated `public` paths; eventual listing images should use this existing path, not manifest filenames as `public_photo_path` or invented image URLs. Private exchange evidence must remain separate. This report does not implement image loading.
- October 11, 2026 schedules are intentional demo snapshots and will need an explicit future fixture refresh for a later demo. Unknown sizes, accessories/models, and availability remain unknown; no unsupported compatibility guarantee is inferred.
