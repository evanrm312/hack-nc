# Campus Current: shared agent instructions

## Project and working style
- Four-person, 24-hour hackathon. Tracks: Gemini, Frutiger Aero, Beginner.
- Build a UNC campus marketplace for buying and borrowing existing items.
- Read BUILD_BRIEF.md and docs/contracts.md if present. If absent, use these instructions and the current task; report missing context.
- Inspect the repository and git status before changing files. Preserve existing work and the team's chosen frontend.
- Implement only the assigned milestone. Explain the behavior and how to test it.
- Honor requests for hints or explanations without completing unrequested implementation.
- Do not add external marketplace search, trade, real payments, additional sponsor services, or new frameworks to this scope.
- Do not launch subagents unless explicitly assigned by the user.

## Stack and execution
- Backend: Python, Flask application factory, Flask-SQLAlchemy, SQLAlchemy 2-style queries, Flask-Migrate, PostgreSQL.
- Default factory: create_app(test_config=None) in server/app.py; server/__init__.py makes server a package.
- Use Flask Blueprints to register separate route groups.
- Default frontend is HTML/CSS/JavaScript with Jinja, but preserve an existing frontend and coordinate its API contract.
- Managed identity and file storage: Supabase. PostgreSQL may be supplied by the same project.
- Gemini is called server-side by Person 2's module, with structured output validated using Pydantic.
- Tests: pytest and Flask's test client.
- Use requirements.txt for runtime dependencies and requirements-dev.txt including runtime requirements plus test tools. Record versions verified in the actual environment.
- Keep setup commands in README.md and update them when behavior changes.
- Run from the repository root.

Commands after the scaffold exists:
~~~sh
python -m pip install -r requirements-dev.txt
python -m flask --app server.app:create_app run --debug
python -m pytest -q
~~~

The development server and debugger are for local use. Deployment uses the team's production WSGI setup and environment configuration.

## Ownership
Person 1 (Evan), backend and integration:
- server/app.py, server/__init__.py, server/config.py, server/db.py
- server/auth/, server/models/, server/routes/catalog.py, server/routes/requests.py
- server/routes/health.py, server/storage.py, server/services/reservations.py
- migrations/, dependency files, .env.example, deployment files
- docs/contracts.md, shared API client, auth UI
- tests/conftest.py, tests/test_health.py, tests/test_auth.py, tests/test_catalog.py, tests/test_requests.py, tests/test_reservations.py

Person 2, Gemini and matching:
- server/intelligence/, matching/normalization/pricing tests and fixtures

Person 3, marketplace and visual design:
- Marketplace templates/pages, shared CSS/assets/components and marketplace JavaScript

Person 4, exchanges:
- server/exchanges/, exchange templates/JavaScript, exchange/review tests

Person 1 coordinates shared schema, migrations, dependencies, application wiring, and API contract changes.
Implement owned files. Report the exact shared change needed when it belongs to another owner, and continue independent work.
Do not modify another person's module to make your task appear complete.
Shared test fixtures belong to Person 1; module-specific fixtures stay in their module's tests.

## Product invariants
- New users can transact without a review-based spending limit.
- Posting and transacting require an authenticated, email-confirmed user with exact normalized domain unc.edu.
- Email verification establishes mailbox control, not student status or personal trustworthiness.
- Public browsing may expose listings and explicitly published, sanitized requests.
- Original request text, exact schedules, private chat, email addresses, and condition evidence are not public by default.
- Requests are private until the requester explicitly publishes them.
- Keep sale price, rental fee, agreed item value, and deposit in separate fields.
- Owner selects collateral from 0 to 100%; default 100%. Below 100% requires explicit lender acknowledgment tied to the current offer revision.
- Explain the uncovered amount in dollars. No guaranteed reimbursement, automated damage charge, or reputation-based collateral discount.
- Payments/deposits are simulated and visibly labeled. No real card data is collected.
- Editing agreed terms resets both acceptances.
- Only the two participants can access exchange messages or condition evidence.
- One physical item has at most one active reservation in this MVP.
- Initial handoff requires condition evidence and both confirmations.
- Loans additionally record photos before and after return. Disputes remain unresolved for manual review.
- Do not penalize refusal of a materially misdescribed item automatically.
- Reviews are tied to actual completed exchanges. Structured answers are required when a review is submitted; comments are optional.

## API and data conventions
- Use /api routes and JSON. Define exact payloads in docs/contracts.md before frontend integration.
- IDs are strings; generate them on the server.
- Money is integer USD cents. Reject negative values, floats, strings, and booleans where an integer amount is required.
- Whole-number collateral percentages use deterministic cent rounding documented in the contract.
- Times are timezone-aware ISO 8601 UTC. Display/interpret campus dates in America/New_York.
- Unknown values are null, not invented defaults. Validate required fields based on buy/borrow mode.
- Use explicit allowed request fields and response serializers. Never mass-assign arbitrary JSON to database models.
- Derive owner/requester/sender identity from verified authentication; never trust IDs supplied to claim ownership.
- Standard error: {"error":{"code":"...","message":"...","fields":{}}}.
- Use 200 for successful reads/updates, 201 for creation, 400 for invalid input, 401 for invalid/missing auth, 403 for prohibited actions, 404 for missing or intentionally concealed resources, and 409 for state conflicts.
- Do not expose stack traces, credentials, private fields, or tokens in API responses or logs.
- Use pagination or a documented small limit for list endpoints.
- Match explanations reference real listing fields. Python applies hard eligibility constraints; Gemini does not decide authorization or enforce money rules.
- Keep Person 2's normalize_request, match_listings, and evaluate_price interfaces in docs/contracts.md; Person 1 owns HTTP integration.
- If a validated comparable price range [L,U] exists: block P>U and 2*P<=L; warn for L>P with 2*P>L. Sale and rental references are separate.
- Never invent price evidence. Missing-data fallback is a team policy choice; document it before enabling price enforcement. Explicit free loans bypass positive rental-price floors.

## Database and authentication
- Initialize extensions independently and call init_app inside the factory.
- Use migrations for shared database changes; never drop production tables or reset a shared database.
- Keep schema business constraints in the database where practical.
- Verify Supabase auth server-side and check confirmed email plus exact domain.
- Never treat decoding an unverified token as authentication.
- External auth failures fail closed. Return a clear service error if verification is unavailable.
- Maintain a local profile keyed by the authenticated provider user ID.
- Browser access must not bypass Flask's private-data and ownership rules. Restrict direct database/storage access appropriately.
- Keep .env, tokens, private keys, local databases, and virtual environments out of Git.
- .env.example contains names and harmless placeholders only.
- Tests may inject a fake identity verifier. No query parameter, header shortcut, or deployed switch may impersonate users.
- Public listing images and private transaction evidence use distinct access policies.
- Validate actual image type, size, and generated storage names. Private evidence is exposed only after participant authorization.

## Reservations
- Person 1 implements a small reusable reservation service; Person 4 owns exchange state transitions.
- Person 4 calls the reservation service when both parties accept the latest offer.
- The availability check, reservation, and accepted exchange update must share a database transaction.
- Use an atomic conditional update or database locking/constraint so two requests cannot both reserve one item.
- The service participates in the caller's transaction; do not independently commit half an exchange.
- Return a state conflict for the losing attempt. Repeated acceptance must not duplicate records.
- Validate PostgreSQL concurrency behavior against isolated PostgreSQL, not only SQLite.

## Person 1 milestone order
M1: Scaffold and health.
- Create the application factory, health Blueprint, config seam, README, dependency files, .gitignore, and .env.example.
- GET /api/health returns 200 and {"status":"ok"}; it proves HTTP availability, not database readiness.
- Add isolated app/client pytest fixtures and health/JSON-404 tests.
- This milestone runs without Supabase, Gemini, SMTP, or database credentials.

M2: Persistence and a small public catalog.
- Connect configured PostgreSQL and add migrations for Profile and Listing.
- Add GET /api/listings and GET /api/listings/<id> with public-field serializers.
- Seed clearly labeled demo data only into an isolated development database.
- Prove records survive a server restart.
- Agree the remaining shared models/interfaces with Person 4, then add them incrementally.

M3: Verified identity and listing mutations.
- Add the authentication adapter and GET /api/me.
- Add POST /api/listings and PATCH /api/listings/<id>.
- Verify ownership, mode-specific required fields, and money validation.
- Return 401/403 as documented. Reject or explicitly ignore forbidden ownership/status fields, consistently.

M4: Requests and teammates' interfaces.
- Add request create/read/update/publish and meeting spots.
- Publishing requires requester ownership; public output is explicitly sanitized.
- Wire Person 2's normalization/matching interface as it becomes available.
- Provide storage and reservation helpers for Person 4.
- Document endpoints with examples and integrate with Person 3.

M5: Deployment and integration.
- Deploy a skeleton early; deploy later milestones incrementally.
- Run migrations as a deliberate deployment step, not on every request.
- Verify email delivery, redirect settings, private storage, and persisted data.
- Rehearse with two accounts and two separate browser sessions.

## Testing and completion
- Tests run without live Gemini calls or real email delivery; substitute external boundaries in tests.
- Every database test uses an isolated temporary database/schema, never the shared application database.
- Use TEST_DATABASE_URL for PostgreSQL integration tests; require an explicit isolated test target and refuse the live DATABASE_URL.
- Do not run destructive cleanup on any database whose test identity is uncertain.
- SQLite may support fast portable tests, but is not evidence of PostgreSQL locking, constraints, or migration correctness.
- Test observable behavior: valid payload, bad payload, missing resource, unauthenticated request, wrong owner, private-data exposure, and competing reservation.
- Relevant focused checks first; then the agreed integration suite before merging.
- Do not call a test successful unless it actually ran.
- Report changed files, behavior, executed checks, remaining blockers, and the next milestone.

