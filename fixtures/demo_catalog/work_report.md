# Catalog assets and services — review report

Work remains uncommitted on `catalog-assets-services`, based on checkpoint `76232ca6580167d9daf98913507ec1375c7402bd`. No branch switch, commit, push, merge, force-push, configured-database write or API-key output occurred during this work.

## Outcome

The preserved 42 listing keys now form a **54-listing catalog**: 33 physical items and 21 services across 12 fictional demo owners. All original physical prices, modes, sizes, collateral and availability terms remain intact. Physical categories were standardized; one unsupported tablecloth description claim about a planned photograph was corrected. Existing service keys/prices/durations were retained while their scope was reconciled with the requested service bank.

There are **52 licensed local reference images and 54 manifest entries**. The requested 54-image goal remains short by two: `clothing-event-tablecloths` and `dorm-storage-bins-pair`. Licensed candidates contradicted the required navy color or clear lidded-bin form; no unrelated substitute was used. The seed tolerates these missing references.

Every new owner is sandbox/demo, every listing title/description visibly identifies demo data, and no new ratings, transactions, completed jobs, credentials, verification claims or impact numbers were generated. Existing labeled legacy price-reference fixtures are retained unchanged.

## Changed files by team owner

**Evan / Person 1:**
- `server/models/listing.py`: central eight-category constant; no schema change.
- `docs/contracts.md`: the identical eight category strings.
- `server/seed.py`: protected JSON-backed catalog/public-photo integration.
- `server/app.py`: forwards the existing development Supabase seed opt-in.
- `tests/test_services.py`: API acceptance/filter/matching for eight categories and unknown-category refusal.
- `tests/test_catalog.py`: preserves legacy coverage while accounting for the expanded catalog and explicitly using local test storage.
- `tests/test_demo_catalog.py`: idempotency, preservation, demo/auth mapping, collisions, guards, storage failure, absent file handling and rollback cleanup.

**Aarush / Person 2:**
- `server/intelligence/normalize.py`: the expanded service categories in structured output/instructions, focused follow-ups, and explicit prohibition of invented qualifications/transport/tools/experience/membership/availability.
- `tests/test_normalization.py`: mocked extraction/category rejection cases.
- `tests/test_matching.py`: all supported service categories through the existing deterministic matcher. Matching implementation and sale/borrow pricing rules remain unchanged.
- `docs/ai-behavior.md`: inputs/examples/limitations and handoff for the expanded categories.

**Emily / Person 3:**
- `static/js/marketplace.js`: eight service choices, canonical item choices, Offer type/Category catalog filters with stale-response protection, service reference-photo rendering, attribution wrapping and removal of the item meeting-spot section from service detail.
- `templates/marketplace/home.html`: catalog-filter container.
- `templates/marketplace/listing_form.html`: expanded service examples.
- `docs/design.md`: current selectors, filters and reference-photo behavior.

**Sid / Person 4 — necessary seed-caller compatibility:**
- `server/exchanges/preview.py`: its isolated database is now `preview_dev.sqlite3`, satisfying the unchanged dedicated-development target guard.
- `tests/test_exchanges.py`: only the existing preview regression test changed. It retains the original two preview examples, accounts for four Alice-owned catalog records, verifies repeat IDs/demo labels/no exchanges, and verifies an old `preview.sqlite3` sentinel remains untouched.
- Existing preview state is not automatically migrated; Sid must review this path change. No old database is deleted or overwritten.

**Team-assigned catalog/image artifacts:**
- Updated the four JSON fixture banks, `validate_catalog.py`, `validation_report.md`, and `integration_handoff.md`.
- Added six provenance fragments in `image_manifests/`, 52 WebPs in the five `images/` groups, five categorized `contact_sheets/`, `validate_images.py`, `test_image_validation.py`, and `image_validation_report.md`.
- Added reproducible `smoke_catalog.py`, observed `smoke_results.json`, and this report.
- Removed obsolete `evan_seed_integration.patch` and `test_seed_proposal.py`; actual integration replaces the old image-free 42-listing proposal. Do not apply an old copy.

No migrations, dependencies, storage adapters, routes, authentication code, exchange lifecycle implementation or unrelated teammate files changed. The initial tree was clean; no concurrent teammate edits were overwritten. The necessary Sid-owned compatibility change was reported before editing and remains flagged for his review.

## Catalog counts

| Kind | Count |
|---|---:|
| Borrow only | 11 |
| Sale only | 11 |
| Sale and borrow | 11 |
| Services | 21 |
| Free to keep (sale price exactly zero) | 4 |
| Free to borrow (rental fee exactly zero) | 8 |
| Free services (service price exactly zero) | 3 |

All money is integer USD cents. Borrowing fee and proposed deposit remain separate. Service payloads contain no item-only fields, and their multiple UTC windows each accommodate the listed 30–120 minute duration. October 11, 2026 dates are deliberate snapshots, never automatically shifted.

| Category | Count |
|---|---:|
| formalwear | 6 |
| dorm essentials | 6 |
| clothing | 1 |
| event equipment | 2 |
| electronics | 10 |
| academic supplies | 2 |
| tools | 1 |
| outdoor gear | 3 |
| mobility | 2 |
| tutoring | 4 |
| proofreading | 3 |
| moving help | 3 |
| tech help | 3 |
| repair and mending | 3 |
| bike repair | 2 |
| photography | 2 |
| event help | 1 |

Exactly eight service categories are supported. The five additions are `tech help`, `repair and mending`, `bike repair`, `photography`, and `event help`; `tutoring`, `proofreading`, and `moving help` remain supported. The string category column needs no migration. Service lifecycle remains negotiating → scheduled → completed, plus cancelled/disputed.

## Image provenance and validation

| Source | Count |
|---|---:|
| Wikimedia Commons | 34 |
| Pexels | 17 |
| Unsplash | 1 |

| License | Count |
|---|---:|
| CC BY 2.0 | 5 |
| CC BY 4.0 | 3 |
| CC BY-SA 2.0 | 2 |
| CC BY-SA 3.0 | 4 |
| CC BY-SA 4.0 | 7 |
| CC0 | 6 |
| CC0 1.0 | 2 |
| Pexels License | 17 |
| Public Domain | 1 |
| Public domain | 4 |
| Unsplash License | 1 |

Total image bytes: **4,700,220 (4.48 MiB)**, excluding review sheets. All 52 assets are readable 1200×900 WebPs, with checked hashes/byte sizes, stripped EXIF/XMP/ICC metadata and stable filenames. Zero orphan files, exact image/source duplicates or 256-bit dHash near-duplicate candidates at Hamming distance ≤20. All 52 were visually inspected. All 34 Commons licenses, the Unsplash source, and 17 official Pexels pages/license were independently checked. Pexels direct HTTP requests returned 403; official pages were read through the web tool.

35 files naturally compress below the soft 100–350 KB target; none exceeds 350 KB. Files were not padded. Some official source thumbnails were upscaled when original downloads were blocked. Manufacturer marks and scene/background limitations are documented in `image_validation_report.md`; there are no recognizable faces, watermarks, personal contact data, UNC branding, or copyrighted artwork/characters as the subject.

All photos are licensed **illustrative references for fictional demo inventory**, not evidence of the listed exact model, dimensions, condition, defects, accessories or provider qualifications. Face-removing crops, bike-brand removal and object/model detail crops were completed and reviewed. BY-SA adaptations carry the same-license notice. Required credit, license, modifications, source URL and the reference disclaimer appear in the seeded public description. Runtime images use generated public-storage paths, never hotlinked/static fixture paths.

The embedded `image_manifest` objects in the four fixture banks are historical sourcing briefs. The six `image_manifests/*.json` files are the authoritative licensed/missing runtime records.

## Seed smoke test — actually executed

Command:

```sh
.venv/bin/python fixtures/demo_catalog/smoke_catalog.py > fixtures/demo_catalog/smoke_results.json
```

The script used existing migrations and Flask's real CLI/test client in a fresh temporary `catalog_dev.sqlite` with temporary local storage, then removed the database/uploads. It never used the configured database or remote storage.

| Result | First run | Second run added |
|---|---:|---:|
| Listings | 56 | 0 |
| Profiles | 13 | 0 |
| Meeting spots | 3 | 0 |
| Existing labeled fixture price references | 2 | 0 |
| Public images | 52 | 0 |

The 56 listings are 54 catalog records plus two preserved legacy suits; the 13 profiles are 12 catalog owners plus the legacy lender. Catalog mode/free/category counts match the tables above. Two catalog images remain missing; the two legacy suits also retain their existing null photos. Duplicate catalog IDs: **0**. Second-run listing serialization and image paths/files were unchanged. All **52 public media URLs returned HTTP 200 image/webp**. Alice authenticated as `clothing-owner-1`; Bob as `services-owner-1`, using the existing hashed sandbox subjects. Other owners remain non-login demo profiles.

The loader preserves user-created and customized demo records, fills only absent photos through the storage adapter, appends missing credit after successful storage, and never replaces existing photos. Unsupported showcase identities stay non-login. Separate old catalog and authentication profiles produce an explicit collision refusal rather than an account merge. Missing local files and storage failures do not block remaining rows; tampered/policy-invalid fixtures are refused. Failed database commits roll back rows and attempt newly uploaded-object cleanup. Development/production target protections and the explicit configured-project Supabase opt-in are unchanged.

## Controlled matching — observed API results

These were **real create-request → get-matches API calls** with editable manual controlled constraints, not live Gemini normalization. Every returned ID was checked against the temporary database. The catalog has one $5 graphing calculator; two explicitly labeled calculator control rows were added only in that disposable database to cover the free-loan/wrong-model cases. They are not additions to the 54 JSON listings or seed.

| Scenario | Confirmed | Needs confirmation | Rejected |
|---|---|---|---|
| Navy 40R suit, $20 fee budget/$80 deposit limit | Navy 40R: 1500-cent fee, separate 5400-cent proposed deposit, known availability | Cheaper black suit: 1200-cent fee, unknown size/date bounds; 10500-cent deposit requires negotiation | Charcoal 44L: explicit jacket-size mismatch (also exceeds deposit limit) |
| Proofreading, 45 minutes, $20, Oct 11 7–9 PM NY | College essay: 1500 cents, duration and ≥45-minute overlap fit | None | Resume/cover letter: 2500 > 2000 cents; lab report: only 30 minutes overlap |
| GC-84 calculator borrow, $10/$90 limits | Catalog $5 option and temporary free control; free loan ranked first with separate 8500-cent deposit | None | Temporary GC-83 control: required-model mismatch |
| Repair/mending, 45 minutes, $20, fitting window | Basic mending ($10) and button/seam mending ($0) | None | Wrong proofreading category; 30-minute repair-assessment duration insufficient |
| Mending, no requested availability | None | Both compatible-duration services: `service_time_windows` missing | Other incompatible listings |
| Mending, conflicting evening window | None | None | No feasible overlap long enough for the requested duration |

All unrelated category/mode rejections remain in total group counts. The focused entries, exact reasons, shortcomings, unknown fields and real temporary database IDs are in `smoke_results.json`. Low-collateral lender acknowledgment remains the existing explicit exchange responsibility; confirmed matching does not accept offer terms or collect money.

## Exact validation commands and final results

```sh
.venv/bin/python -m pytest -q tests/test_normalization.py tests/test_matching.py tests/test_services.py
# 192 passed in 3.48s

.venv/bin/python -m pytest -q tests/test_catalog.py tests/test_demo_catalog.py
# 16 passed in 14.20s (integrator)

.venv/bin/python -m pytest -q fixtures/demo_catalog/test_image_validation.py
# 16 passed in 3.66s (validator; this folder is outside pytest.ini testpaths)

.venv/bin/python -m pytest -q tests/test_exchanges.py::test_preview_uses_isolated_labeled_data_and_does_not_duplicate_inventory
# 1 passed in 2.63s after preview compatibility fix

.venv/bin/python -m pytest -q
# FINAL: 373 passed, 1 skipped in 29.27s

.venv/bin/python fixtures/demo_catalog/validate_catalog.py
# Passed: 54 fixture payloads through existing backend listing validation,
# service/item matching exercise, counts and image checks (validator)

.venv/bin/python fixtures/demo_catalog/validate_images.py
# Passed: 54 manifest keys, 52 licensed assets, 2 explicit missing (validator)

node --check static/js/marketplace.js
# Passed

git diff --check
# Passed
```

The first post-integration full run found the preview's unnamed target incompatibility (1 failed, 372 passed, 1 skipped); the dedicated `_dev` path/test fix resolved it without relaxing guards. The final full run above passed. The one skipped test requires `TEST_DATABASE_URL`, which is not configured. Gemini unit tests were mocked; **zero live Gemini calls** were performed for this assignment. Public-source licensing reads were live. No Supabase/PostgreSQL deployment or remote-storage test is claimed.

Browser verification could not run: the in-app browser is unavailable and native Chrome computer-use permissions remain pending. The temporary preview server was stopped. Syntax/API/static review passed; interactive UI validation is still for Emily/Sid.

## Required review / remaining gaps

- **Evan:** shared category/contract/seed/CLI/tests, protected target selection, public-storage behavior and explicit auth collision policy. Runtime packaging must include fixtures and validators.
- **Aarush:** mock extraction, deterministic matching examples, fictional model labels, photo limitations and static October 11 demo dates.
- **Emily:** eight selectors/catalog filters, service images, attribution/reference disclosure wrapping; perform the browser check when browser permissions are available.
- **Sid:** preview database filename/test change; preserve/reconcile an existing old preview database deliberately, then check interactive exchange demo journeys. No transactions were seeded.
- **Images:** accurate licensed navy tablecloth and clear lidded-bin photos remain missing. The 54-image goal is incomplete at 52; catalog seeding continues safely.

Nothing is staged or committed. The branch and checkpoint are unchanged. No ownership conflict with concurrent work was found; the small Sid-owned direct-caller compatibility change is explicitly identified for review.
