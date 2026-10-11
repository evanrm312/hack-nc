# Demo catalog validation

The catalog contains **54 DEMO listings** across **12 fictional demo owners**. All 42 checkpoint keys and owners are preserved. All 33 physical specifications, modes, prices, values, collateral proposals, condition, accessories, defects and availability are unchanged. All original nine service keys, prices and durations remain intact; subjects/titles and additional windows were updated for the requested service bank.

| Group | Count |
|---|---:|
| Physical items | 33 |
| Services | 21 |
| Borrow only | 11 |
| Sale only | 11 |
| Sale and borrow | 11 |
| Free to keep | 4 |
| Zero-fee borrow | 8 |
| Free services | 3 |

Exact service distribution: tutoring 4; proofreading 3; moving help 3; tech help 3; repair and mending 3; bike repair 2; photography 2; event help 1. All service durations are 30–120 minutes. Every service has multiple ordered UTC windows supporting October 11, 2026 in New York, and each window fits the offered duration. Services contain no item-only fields.

Physical category normalization: `academics` → `academic supplies`, `outdoors` → `outdoor gear`, `event supplies` → `event equipment`, and steamer `appliances` → `dorm essentials`. The existing statistics service now demonstrates introductory physics under its original stable key. The tablecloth description no longer claims that a missing photo proves a defect.

Executed `.venv/bin/python fixtures/demo_catalog/validate_catalog.py`: passed exact counts, stronger 11/11/11/4/8 distribution minima, field whitelists, integer money/mode consistency, date/duration checks, owner/key references, demo labels, unique titles/descriptions, prohibited-claim/contact checks, all 54 payloads through the actual shared listing validator in a temporary SQLite database, and suit/proofreading deterministic matching checks with listing-key membership. No configured application database was seeded.

A comparison using `git show 76232ca6580167d9daf98913507ec1375c7402bd:<fixture>` independently checked original keys/owners, all physical terms/specifications/availability and original service prices/durations. All passed.

Image validation: **54 entries, 52 licensed local WebPs, 2 missing**. See [image validation report](image_validation_report.md) for live provenance checks, contact sheets, licensing and size limitations. Embedded image manifests are historical plans; `image_manifests/*.json` is authoritative runtime provenance.

The physical calculator bank still has one paid borrowing option. Incompatible-model and free-with-separate-deposit demonstrations therefore require clearly labeled controlled synthetic listings, without changing the preserved physical catalog.

Protected seed integration, repeated seeding and full API flow are reported by the integrator/root after this fixture validation. No browser check is claimed by this report.
