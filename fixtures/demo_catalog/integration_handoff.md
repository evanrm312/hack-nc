# Catalog integration review

The current team assignment authorizes actual integration in `server/seed.py` and the seed CLI. The old unapplied `evan_seed_integration.patch` and disposable patch runner were removed because they describe the previous 42-listing, image-free proposal and no longer apply. Do not apply an old copy.

## Protected loading

Run existing migrations and `flask --app server.app seed-demo` only against a deliberately selected development database. The original `validate_demo_seed_target` implementation is unchanged, and both the CLI and direct `seed_demo_data` calls enforce it. The existing `--allow-supabase-postgres-dev` flag is forwarded; it still requires the configured project's session-pooler database and `APP_ENV=development`. Production, memory SQLite and unnamed targets remain rejected.

`_catalog_plan()` reads all four JSON fixture banks, validates their envelope/distribution, validates the licensed image manifests and bytes, and preflights every listing with the existing HTTP field validator before writes. Stable UUID5 IDs retain the original proposal namespace: `campus-current:demo-catalog:v1:<kind>:<key>`. Wrapper metadata never becomes an API/database field. Runtime deployment must include `fixtures/demo_catalog/` and its validators and Pillow, which is already installed in this project environment.

The loader retains the legacy two suits, lender, three meeting spots and two explicitly labeled fixture price-reference rows. A fresh target therefore contains **56 listings and 13 profiles**: 54 catalog listings/12 owners plus the two legacy suits/one lender. The catalog alone has 33 physical items and 21 services. No transactions, ratings, reviews, impact or verification claims are generated.

## Showcase identities and preservation

`clothing-owner-1` uses the already supported sandbox Alice identity; `services-owner-1` uses Bob. The authentication resolver determines their exact hashed subjects. Mapping occurs only in sandbox auth when that identity is actually configured; otherwise the owner remains a non-login namespaced demo profile. Other owners always use `sandbox:demo-catalog:v1:<key>`, not login credentials. All created profiles are `verification_source="sandbox"`, `is_demo=True`, with visible demo display names. Existing authentication-created sandbox profiles keep their public name and remain visibly demo through `is_demo` and the sandbox badge.

Existing namespaced showcase profiles can adopt a supported sandbox subject without changing their ID. If both that old profile and the supported auth profile already exist separately, the loader fails closed rather than merging accounts or reassigning listings; Evan must resolve that explicit identity collision. Any non-demo/non-sandbox owner or foreign-owner listing collision is refused. Existing matching catalog rows preserve customized titles, description content, prices, specifications, scheduling, status and photos. A successfully filled missing photo appends its required reference disclosure/credit. Unrelated rows are untouched. The existing legacy suit's established missing-type/date-bound upgrades remain intact.

## Public reference photos

Licensed WebPs are saved through `get_storage().save("public", stream, MAX_UPLOAD_BYTES)`. Only a successfully returned storage path is assigned; fixture filenames and remote URLs are never substituted. The existing media route serves the photos. Repeat seeds skip every non-null photo path and do not duplicate uploads.

New descriptions contain visible attribution, license/adaptation terms and source page links plus a clear disclaimer: licensed illustrative references depict fictional demo inventory/provider scenes, not proof of model, size, condition, accessories or qualifications. Existing description content is preserved. For an older matching demo row without credit, the loader preflights the appended disclosure/credit against the HTTP description-length limit and appends it only after a missing photo is saved successfully. Existing non-null photos remain untouched.

Two manifest entries remain explicitly missing (navy tablecloths and clear storage bins), so those listings seed without a photo. Missing references, including unexpectedly absent local licensed files, do not block the catalog. The loader uses the validator’s explicit tolerant missing-file mode; it still validates safe paths and license metadata and strictly checks every present file. Storage failures are reported by listing key without exception text, credentials or request text; failed rows keep null paths and the rest of the catalog continues. A failed database transaction rolls back rows and attempts deletion of newly saved objects. A failed cleanup is logged without secrets and requires operator cleanup. Malformed fixtures, unsafe paths, modified hashes or licensing metadata failures refuse the load before database/storage writes.

## Review and validation

Focused integration commands:

```sh
.venv/bin/python -m pytest -q tests/test_catalog.py tests/test_demo_catalog.py
```

These tests use migrated temporary named development SQLite databases and local temporary uploads only. They cover repeat seeding and file counts, existing auth profile reuse, old namespaced owner compatibility, user/customized-row preservation, public media retrieval, demo labels, ID collision refusal, direct target guards, unsupported showcase identities, storage failure, fixture validation refusal and commit rollback/upload cleanup. No configured database, Supabase storage, deployment or live Gemini call is exercised.

Evan: review shared loader/CLI/tests, target opt-in and identity collision policy before using a real development target. Emily: review attribution wrapping, licensed-reference disclosure, service photo presentation and eight-category selectors/filters. Aarush: review fixture/matching scenarios and representative-photo limitations. Sid: run the interactive demo journeys; the catalog creates no completed jobs or exchanges. October 11, 2026 windows are deliberate snapshots, not automatically shifted dates.

## Exchange preview compatibility (Sid review)

The isolated preview caller now uses `preview_dev.sqlite3`, a named development target accepted by the unchanged direct-call guard. An existing `preview.sqlite3` is left untouched; its prior preview state is not migrated automatically. This minimal compatibility update changes only that tooling path and its existing regression test. Alice now owns the mapped clothing showcase records plus the preview's original two demonstration listings. The test verifies both original demo titles, catalog presence, stable owner inventory IDs on repeated setup, demo labeling, no exchanges, and preservation of the old file. Sid should review the changed preview path before resuming a saved preview session.
