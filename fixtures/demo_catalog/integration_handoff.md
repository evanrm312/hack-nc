# Evan handoff: proposed catalog seed integration

The 42 catalog listings and 12 fictional owner definitions remain JSON fixtures. No configured database was contacted or seeded. No shared file was edited. Images remain planned, with permission/attribution pending.

## Exact proposed shared change

Review `fixtures/demo_catalog/evan_seed_integration.patch`. It changes only `server/seed.py` and the existing seed CLI's one call in `server/app.py`. The patch is an unapplied proposal for Person 1; catalog generation stops at this boundary.

The existing `flask --app server.app seed-demo` command would load the catalog alongside the existing three meeting spots, demo lender, two suit records, and two fixture price references. Existing legacy seed behavior remains unchanged. The catalog adds no price evidence, reviews, transactions, verification claims or images.

- Keep the CLI's existing `validate_demo_seed_target` call, including its explicit Supabase development opt-in. Forward that flag to `seed_demo_data`, which repeats the unchanged guard for direct callers. Production and unnamed databases remain rejected. Supabase `/postgres` still requires the configured project's session-pooler URL and `--allow-supabase-postgres-dev`.
- Reuse `validate_catalog.validate()` for all four files' shape/metadata/cross-file checks, then preflight every body using the existing `_apply_listing_fields(..., creating=True)` HTTP validator before adding any catalog row. Keep the fixture directory and validator available in the runtime checkout/package.
- Owner identity is `sandbox:demo-catalog:v1:<owner-key>`. It is a fictional namespaced subject, not an email or login credential. Profile and listing IDs are stable opaque UUID5 hex values over `campus-current:demo-catalog:v1:<kind>:<key>`; no new schema field is needed. Display names remain visibly demo; profiles set `verification_source="sandbox"`, `is_demo=True`, and the existing allowed domain field. The public badge says sandbox, not verified.
- Repeated loads skip existing catalog rows by stable identity. Edited prices, titles, availability, reservations, statuses, photos and demo display names remain untouched. No row is deleted. Unexpected profile ID/subject collisions, non-demo/non-sandbox profiles, or listing IDs with different owners or absent demo labeling fail closed. All catalog inserts participate in the existing final transaction/commit. If any later operation or commit fails, callers must roll back the session, as with existing seed errors.
- Do not add `source_agent`, `is_demo`, owner keys, seed keys, image manifests or generated IDs to the listing API body. Use existing Listing columns and wrapper metadata only.

## Observed focused validation

Commands actually executed:

```sh
git apply --check fixtures/demo_catalog/evan_seed_integration.patch
.venv/bin/python fixtures/demo_catalog/test_seed_proposal.py
```

Both passed. The second command copies the two proposed shared files into a disposable directory, applies the patch there, compiles the candidate seed module without changing/import-replacing repository modules, applies the two existing migrations to a temporary `catalog_dev.sqlite`, and removes everything at exit. It does not apply the patch to this repository or use `.env` database configuration.

Assertions passed: 42 newly inserted catalog listings; 12 new owners; 45 total listings and 14 profiles with two existing demo listings plus one controlled user row; unchanged legacy demo and user records; second load creates nothing; edited catalog record stays unchanged; every new owner is labeled sandbox/demo; every catalog photo path stays null; production guard rejection; required Supabase opt-in and configured-project check; non-demo profile and foreign-owner listing collision rejection; a last-entry API validation failure causes zero partial catalog inserts.

The fixtures' separate validator already reports 11 borrow-only, 11 sale-only, 11 sale-and-borrow, 9 services, 4 free-to-keep and 8 free-to-borrow. This proposed-loader check is local SQLite only: no Supabase connection, authenticated upload, live Gemini request, or deployment check was performed.

## Person 1 integration steps

1. Review the proposed patch and the unchanged target guard; check against latest shared files. Apply it only in Person 1's authorized branch. `git apply --check fixtures/demo_catalog/evan_seed_integration.patch` verifies context; `git apply fixtures/demo_catalog/evan_seed_integration.patch` is the proposed application command, **not executed here**.
2. Add/adjust Person 1-owned seed CLI tests for the forwarded opt-in and direct-call guard. Run the seed/auth/catalog suites and full suite, including named temporary development targets.
3. Apply existing migrations to the deliberately selected development target. Run the existing seed command; for the designated Supabase development database use its existing explicit `--allow-supabase-postgres-dev` flag. Run twice and verify catalog IDs and edited/demo/user rows remain stable. Do not target production.
4. Verify public catalog serialization shows the demo title/description and sandbox owner badge. Namespaced catalog owners cannot authenticate by ordinary sandbox emails; if interactive negotiation is needed, Evan must choose a deliberate demo-owner authentication mapping rather than impersonating real identities.

## Deferred image and service wiring

Storage is understood: `get_storage().save("public", stream, MAX_UPLOAD_BYTES)` checks magic bytes for JPEG/PNG/WebP, caps size and returns a generated relative `StoredFile.path`. Only that returned path belongs in `Listing.public_photo_path`; never put manifest filenames, source URLs or arbitrary remote URLs there. Existing local and Supabase adapters and public media route handle delivery. Private evidence stays in the separate private scope. All catalog photo paths are null; no image was downloaded, committed, acquired or loaded. A later explicitly authorized image pass must resolve permission/attribution and either use the authenticated existing photo endpoint as the owner or an Evan-reviewed seed storage helper.

Service listing bodies deliberately omit all item fields and specifications, per today's contract. Subject/scope lives only in descriptions; the deterministic matcher must ask for confirmation for structured requirements it cannot verify. Subject/spec storage requires an Evan-owned contract/schema decision. Emily can display these demo listings through the existing catalog API once Evan loads them. October 11, 2026 dates are intentional snapshots; a later demo needs an explicit fixture update, not automatic date shifting.
