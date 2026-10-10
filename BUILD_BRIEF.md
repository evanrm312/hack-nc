# Campus Current: 24-hour build brief

Working name only. Team: four people. Confirmed targets: Gemini, Frutiger Aero, and Beginner. This is a proposed implementation plan, not an already-built application. Check organizer rules for Beginner eligibility and permitted AI assistance before submission.

## 1. Product and scope decision

Campus Current helps UNC community members describe an item they need, find a compatible item to buy or borrow, negotiate the terms, and coordinate a campus exchange.

The demonstrable value is matching a need to an available existing object, including specifications, dates, budget, and collateral affordability. The environmental mechanism is reuse and sharing. Count completed exchanges and loans, not invented carbon savings.

Primary demo: a new user needs a suit for an interview. Gemini extracts size, budget, deadline, and borrowing preference. The app excludes incompatible offers. The lender voluntarily accepts a smaller deposit, both users accept an agreement, and the exchange is tracked through pickup and return.

Build a functional web app. External marketplace aggregation, Photon, Tiger Data, and Snowflake are outside this weekend's recommended scope. They can be future work. This is an explicit scope recommendation, not a claim that earlier ideas were unnecessary.

## 2. Collateral policy

Use owner-selected collateral with explicit agreement. Do not require new users to complete unrelated purchases before borrowing a valuable item.

Keep these amounts separate:

- Sale price: purchase payment.
- Rental fee: payment for temporary use, possibly zero.
- Agreed item value: the agreed reference value for non-return, not a guarantee of market value.
- Deposit: security proposed for the borrowing transaction.
- Amount not covered by deposit: max(agreed item value - deposit, 0).

Example: agreed value $200, rental fee $15, deposit 30% = $60. The lender explicitly accepts $140 of item value not covered by the deposit. The borrower's immediate cash/credit requirement in a real payment version would include the $15 fee and $60 deposit, subject to the eventual payment method.

Recommended prototype policy:

1. Default proposed collateral to 100% of agreed item value.
2. Let the lender choose 0-100%; lowering it is voluntary.
3. Show the deposit in dollars and percentage, and the dollar amount not covered.
4. Require a specific lender acknowledgment when deposit is below item value.
5. Any change to fee, value, deposit, dates, location, or condition resets both acceptances.
6. New users have the same starting eligibility; there is no monthly spending cap or level requirement.
7. Reviews inform the lender but never automatically lower collateral.
8. The platform does not guarantee compensation or automatically forgive liability beyond the deposit. Liability and claim terms must be stated separately before a real launch.
9. If both sides cannot agree on affordable collateral, no loan occurs.

For the hackathon, simulate deposit status and payment. Every affected screen must say that no real funds are reserved or charged. Never display "funds secured" for a database-only status. Do not collect card numbers. A real payment integration, authorization expiry handling, and financial claims process are later work.

An actual hold would have a capture deadline, and collected charges can still be disputed. Reference: Stripe documentation in the sources section.

## 3. Complete user journey

### A. Account

- Users can browse public listings and sanitized public requests.
- Posting, messaging, making offers, and reviewing require a verified @unc.edu email.
- Validate the exact normalized domain on the server and actual email confirmation, not merely a text suffix in the browser.
- Call the badge "UNC email verified." This is not proof that someone is a student or trustworthy.
- Never publish the full email address.
- Demo profiles must be labeled if they did not complete real verification.

### B. Request

Inputs:

- Original natural-language description.
- Buy or borrow (allow either as a search preference).
- Required specifications and preferred specifications.
- Needed-by deadline; borrowing use start and end.
- Acceptable pickup windows and campus area.
- Purchase/rental budget, separate from maximum deposit affordability.

Gemini proposes normalized fields. The user can edit them before searching. Resolve vague times such as "2 a.m." to an explicit date in America/New_York and ask for confirmation. Persist timestamps in UTC. Unknown information stays unknown. Unknown required compatibility appears as "needs confirmation," not a guaranteed match.

If the user finds no suitable offer, show an explicit Publish Request button. Let the user preview the public fields. Keep precise schedules and contact information private. Requests close when fulfilled, cancelled, or expired.

### C. Listing

Owner provides:

- Item title, category, description, photo, specifications, known defects/accessories.
- Allowed modes: sale, borrowing, or both.
- Asking sale price and/or rental fee.
- Borrowing availability and agreed-value proposal.
- Deposit percentage proposal.
- Preferred public meeting locations.

For the MVP, each physical item has only one active reservation. No multi-quantity inventory or calendar of future overlapping reservations.

### D. Matching

1. Gemini normalizes language and synonyms using structured output.
2. The server validates the extracted structure.
3. Deterministic code checks mode, known required specifications, dates, budget, deposit affordability, and item availability.
4. Rank eligible results by preference fit, cost, pickup compatibility, and availability certainty.
5. Show concrete reasons for a match and known shortcomings.
6. Separate confirmed matches from options needing confirmation.
7. Every result must reference a real current database listing.

A free loan can still be unaffordable if the deposit exceeds the user's limit. Treat fee and deposit as separate constraints.

### E. Negotiation and agreement

Provide a private conversation per proposed exchange. Polling every few seconds is sufficient; do not build WebSockets for the MVP.

Chat supports discussion. A structured offer card records the current terms:

- listing, participants, buy/borrow mode
- sale price OR rental fee
- agreed item value and deposit for loans
- pickup location and time
- return location and deadline for loans
- condition/accessories agreement
- offer revision number and participant acceptances

Only the two participants can read or modify the exchange. Only the owner can offer their item. Both accept the same current revision. A server-side reservation operation must reject competing acceptance if the item has already been reserved. Repeated button presses must not create duplicate agreements.

### F. Handoff

- Upload condition photo(s) immediately before initial handoff.
- Both parties acknowledge condition and included accessories.
- Buyer can reject a materially misdescribed item without an automatic cancellation penalty.
- Both confirm possession changed.
- Purchase: exchange can complete.
- Borrowing: exchange becomes active.

Listing photos and condition evidence serve different purposes.

### G. Return

- Borrower uploads photo(s) before returning.
- Owner uploads photo(s) after receiving.
- Both can acknowledge the condition record.
- Owner accepts return or raises a specific issue.
- A contested return becomes disputed; a photo alone cannot resolve it.
- For the prototype, disputed exchanges remain flagged for manual review and do not trigger automatic charges.
- Do not build a financial adjudication engine.

### H. Review

- Reviews belong to completed transactions and actual participants.
- Borrowing reviews occur after return/completion.
- Stars plus required structured selections when submitting: description accuracy, agreed condition, punctuality, communication, and timely return where relevant.
- Each field supports not applicable/unable to assess.
- Comment optional.
- One review per participant per exchange.
- Show number of reviews and relevant loan history.
- Recommendation: feedback is optional to submit; completing a transaction should not force a review.
- Delayed mutual publication is stretch work; if unavailable, acknowledge retaliation remains a limitation.
- Cosmetic progress can be added later. No financial privileges tied to points.

## 4. Price-range rule

Retain the team's requested rule where a validated comparable range exists: Let L be its lower bound, U its upper bound, and P the final agreed price.

- Block P > U.
- Block P <= 0.5 * L.
- Warn when 0.5 * L < P < L.
- Allow L <= P <= U.

Use integer cents: the lower rejection can be implemented as 2 * P <= L. Test the boundaries explicitly.

Requirements:

- Sale ranges and rental-fee ranges are separate; rental duration matters.
- Do not derive deposit or item value from a rental-fee range.
- Record category, condition, model/specifications, observation dates, sample size, and source.
- Compute displayed bounds from documented comparable data; Gemini may help classify comparables but may not invent completed transactions.
- Freeze the applicable range version with the offer so the rules do not silently change after acceptance.
- Support correction of wrongly classified items.
- Free loans are an explicit separate case, not rejected by a positive rental-price floor.

Recommended cold-start fallback: if no defensible range exists, show "insufficient comparable data" and use advisory-only pricing. This is an explicit relaxation for team approval, not a hidden exception. If the team insists on hard bounds for every transaction, restrict the demo to categories with clearly labeled reviewed fixture ranges. Do not present fixture transactions as real platform history.

Implementation priority: after the main exchange works. This policy is not an anti-fraud guarantee and can exclude legitimate bargains.

## 5. Screens

| Screen | Necessary content | Owner |
|---|---|---|
| Sign-in | Email verification, session status | Person 1 |
| Home / requests | Natural-language request, browse, public requests | Person 3 |
| Search results | Editable interpretation, matches, reasons, no-match publication | Person 3 |
| Listing form/detail | Photo, specifications, modes, asking terms | Person 3 |
| Exchange room | Messages, offer revision, acceptances, meeting and deposit terms | Person 4 |
| My exchanges | Pickup, active loan, return status, photos, review action | Person 4 |

Use shared components and one theme. Person 4 consumes the styles Person 3 defines, without independently redesigning them.

## 6. Recommended stack

Assumption: the team is comfortable with Python and basic browser JavaScript, consistent with Evan's current work. If the team already has a working familiar stack, keep it rather than switching during the event.

- Flask for the web server and JSON endpoints.
- Jinja templates, HTML, CSS, and vanilla JavaScript for the frontend.
- SQLAlchemy with hosted PostgreSQL for persisted application data.
- Supabase can supply PostgreSQL, email authentication, and image storage in one project.
- Gemini via the official Python SDK, called only from Flask.
- Pydantic for AI result validation.
- pytest for matching, pricing, authorization, and state-transition tests.
- One deployment serving pages and API from the same origin.

Application data access:

- Browser obtains an auth session through the selected managed auth flow.
- Flask verifies the session/token and confirmed email server-side.
- All marketplace mutations go through Flask.
- Flask enforces participant/owner authorization on every endpoint.
- PostgreSQL tables and private storage must not be broadly accessible from the public client.
- Backend-only credentials never appear in browser JavaScript.
- Condition evidence and messages are private. Public listing images are separate.
- Configure email delivery and redirects immediately. Supabase's default email sender is restricted; test with the team's actual addresses and configure delivery if needed.
- If email setup blocks the demo, use an explicitly labeled sandbox with isolated seeded users, not a public verification bypass.
- Pick one host with a known Python deployment path and deploy a skeleton in the first two hours.

No separate frontend server, vector database, microservices, additional sponsor database, or real payment dependency is needed for this demo.

## 7. Module ownership for four people

### Person 1: Backend foundation and integration lead

Suggested role for Evan if he is most comfortable with Python.

Owns:

- server/app.py, server/auth/, server/models/, server/routes/catalog.py, server/routes/requests.py
- server/storage.py, server/db.py, migrations/
- templates/auth/, static/js/auth.js, static/js/api.js
- dependency manifest, environment example, deployment configuration
- docs/contracts.md and shared interface changes

Deliverables:

1. Runnable and deployed skeleton.
2. Auth verification and profiles.
3. Shared database models and migrations for the whole team.
4. Listing/request CRUD and integration endpoints for Person 2.
5. Auth and storage helpers consumed by Person 4.
6. Integration merges and deployment checks.

Done when: a verified user can create a listing, another can retrieve it, unauthorized mutation is rejected, and records survive a deployed restart.

### Person 2: Gemini and matching

Owns:

- server/intelligence/
- tests/test_matching.py, tests/test_normalization.py, tests/test_pricing.py
- fixtures/matching/, docs/ai-behavior.md

Deliverables:

1. Validated request normalization and follow-up questions.
2. Matching over real listing records.
3. Grounded match explanations.
4. Missing-information and API-failure behavior.
5. Price-range logic only after matching works.
6. Later assists Person 4 with business-rule tests.

Done when: ten representative requests produce appropriate structured constraints or clear follow-up questions, and matching never ignores a hard requirement or invents inventory.

This person does not own authentication, HTTP routing, shared schema, or app-wide UI.

### Person 3: Frutiger Aero and marketplace UI

Owns:

- templates/base.html, templates/marketplace/
- static/css/, static/assets/
- static/js/marketplace.js, static/js/components.js
- docs/design.md

Deliverables:

1. Shared visual system and responsive shell.
2. Home, request input, results, listing form/detail, public request feed.
3. Loading, empty, validation, and error states.
4. Shared card, button, modal, status, and form styling for Person 4.
5. Visual polish and screenshots for submission.

Done when: the entire discovery/listing journey works against the real endpoints on a phone-size viewport and desktop, with keyboard-visible controls and readable content.

### Person 4: Transaction workflow and demo QA

Owns:

- server/exchanges/
- templates/exchanges/, static/js/exchanges.js
- tests/test_exchanges.py, tests/test_reviews.py
- docs/demo.md

Deliverables:

1. Private messages and versioned offers.
2. Mutual acceptance, simulated collateral acknowledgment, and meeting selection.
3. Pickup/return confirmations and condition uploads.
4. Structured reviews and visible dispute state.
5. Two-browser end-to-end testing and the demo script.

Done when: two users can complete one sale and one loan, a third user cannot read their chat/photos, and a disputed return cannot silently complete.

Person 4 starts from the shared schema. Person 1 supplies auth, storage, and reservation helpers; Person 2 assists with tests after matching is integrated. Person 4 should not also build live payments.

## 8. Shared contracts: freeze before parallel coding

Person 1 prepares these with all four people in the first 60-90 minutes. Everyone branches from that scaffold.

Conventions:

- IDs are strings.
- All money uses integer USD cents.
- Timestamps are ISO 8601 UTC; the UI displays America/New_York.
- Missing values are null/unknown, not zero.
- Error shape: `{"error":{"code":"...","message":"...","fields":{}}}`.
- Browser code uses one shared API helper.
- Every protected operation derives user identity from verified auth, never a client-provided user_id.

Core records:

- Profile: id, display_name, confirmed_email_domain, created_at.
- Listing: id, owner_id, title, category, specifications, condition, accessories, sale_price_cents, rental_fee_cents, proposed_item_value_cents, collateral_percent, availability, meeting_spot_ids, status, public_photo_path.
- NeedRequest: id, requester_id, original_text, normalized requirements, modes, budget_cents, max_deposit_cents, dates, area, visibility, status.
- Exchange: id, listing_id, owner_id, requester_id, source_request_id, mode, status, current_offer_revision.
- OfferRevision: exchange_id, version, monetary terms, condition snapshot, meeting details, dates, pricing_range_version, explicit lower-deposit acknowledgment, acceptance records.
- Message: exchange_id, sender_id, body, created_at.
- Evidence: exchange_id, uploader_id, stage, private_storage_path, created_at.
- Review: exchange_id, reviewer_id, reviewee_id, stars, structured answers, optional comment.
- MeetingSpot: id, label, public area, opening/access notes.
- PriceReference: comparable category/specs/condition, sale/rental type, duration basis, lower/upper cents, sample count, source, fixture flag, version.

Core endpoint boundaries:

- Person 1: /api/me, /api/listings, /api/requests, /api/requests/normalize, /api/requests/{id}/matches, /api/requests/{id}/publish, /api/meeting-spots.
- Person 4: /api/exchanges, /api/exchanges/{id}/messages, /offers, /accept, /evidence, /handoff, /return, /review, /cancel, /dispute. The suffix endpoints are under /api/exchanges/{id}/.
- Person 2 supplies normalize_request(text, now, timezone), match_listings(request, listings), and evaluate_price(price, reference), with documented inputs/outputs. It does not create a second competing API.
- Person 3 consumes Person 1 endpoints; Person 4 consumes the same API helper and UI styles.

Status rules:

- negotiating -> reserved only after both accept the latest offer and an atomic availability check succeeds.
- reserved -> completed for a sale only after required evidence and both handoff confirmations.
- reserved -> on_loan for borrowing after equivalent pickup confirmation.
- on_loan -> return_pending when return is initiated.
- return_pending -> completed after required before/after evidence and mutual confirmation.
- accepted return disputes -> disputed, never automatic charge.
- cancelled releases an unused reservation; it cannot erase an active loan.
- Price, collateral, meeting, or date edits reset acceptance.
- Completed sales mark the listing sold. Completed loans restore availability.
- Duplicate actions are safely rejected or idempotent.
- No double-booking: for the MVP, reserve one active exchange per physical item atomically.
- Cancellation reasons are recorded. There are no automatic financial cancellation penalties.

## 9. Codex and Claude Code workflow

Each human owns one module, one branch, and one primary coding-agent session. This is enough concurrency for a beginner team. Do not launch a fleet of unattended agents.

Either tool can implement any module. Suggested allocation, purely for coordination:

- Person 1: Codex as primary implementer.
- Person 2: Codex as primary implementer.
- Person 3: Claude Code as primary implementer.
- Person 4: Claude Code as primary implementer.

For cross-review, use the other tool in read-only review mode after a small milestone. Tools do not enforce ownership simply because they have different names; the human assignment and file boundaries do.

Git:

1. One repository and a shared main branch.
2. Person 1 creates scaffold, models/contracts, dependencies, and initial deployment.
3. Each person uses a separate clone or worktree and a feature branch.
4. Only one agent writes in a given working directory at a time.
5. Merge small working increments every 1-2 hours.
6. Person 1 coordinates schema, dependency, routing, and deployment changes.
7. Sync main after each integrated milestone.
8. Commit before switching tools; give the next tool the current task, diff, checks, and remaining issue.
9. No force-pushing shared branches or broad unrelated refactors.
10. If a task is blocked by a shared contract, report the exact needed change and continue independent work.

AGENTS.md is instruction context, not an agent scheduler, task lock, or automatic merge coordinator.

Recommended project documents:

- BUILD_BRIEF.md: this plan.
- AGENTS.md: concise shared rules.
- CLAUDE.md: imports shared instructions.
- docs/contracts.md: exact API examples and schemas, maintained by Person 1.
- docs/tasks.md: small tasks with owner, branch, acceptance criteria, status.
- docs/demo.md: demonstration and fallback sequence.
- README.md: verified local setup and deployment steps.

Codex reads AGENTS.md. Claude Code supports shared project instructions and @file imports. Verify the instructions loaded in your installed version. Keep one source of rules rather than maintaining two diverging copies.

## 10. Agent task template

```
Read AGENTS.md, BUILD_BRIEF.md, and docs/contracts.md.

You are implementing [specific milestone] on branch [branch].

Owned files: [paths].

Other modules are being developed concurrently. Do not edit their files.

Goal: [one observable user behavior].

Inputs/outputs: [contract examples].

Acceptance criteria:
1. [happy-path result]
2. [permission or edge-case result]
3. [meaningful validation]

Implement the smallest complete change for this milestone.

If a shared contract must change, explain the exact change and continue
independent work. Do not add unrelated features or dependencies.

Run the applicable checks. Finish with changed files, observed behavior,
checks actually run, and remaining limitations.
```

### Person 1 first task

Scaffold the Flask app and shared schema/contracts described in this brief. Implement verified identity helper, /api/me, listing create/read, and request create/read. Provide reusable auth, storage, and atomic reservation interfaces. Deploy the skeleton and document actual run/test commands. Do not implement Gemini prompts or transaction UI. Prove listing ownership enforcement with two users.

### Person 2 first task

Implement normalize_request and match_listings against agreed schemas and fixtures. Use Gemini structured output with server validation. Preserve unknowns, separate required/preferred fields, and flag ambiguous dates. Test at least ten cases, including wrong size, exceeded deposit budget, unavailable date, missing required specification, prompt-like listing text, and Gemini timeout. Do not edit HTTP routes or shared models.

### Person 3 first task

Implement the shared Frutiger Aero shell and the request-to-results journey. Use the agreed API contract and isolated fixture responses until endpoints land. Create reusable form/card/status styles for Person 4. Show normalization edits, a genuine no-match state, and explicit publication. Include keyboard focus, readable contrast, reduced-motion behavior, and mobile layout. Do not implement alternate backend business rules.

### Person 4 first task

Implement negotiating -> reserved with private messages, versioned offers, mutual acceptance, meeting selection, and simulated collateral disclosure. Use the provided authentication and atomic reservation helpers. Test that a third party cannot access the exchange, edits reset acceptance, and competing users cannot reserve the same item. Then add pickup and return milestones as separate tasks.

### Cross-review prompt

Review this branch's diff without modifying files. Prioritize unauthorized access, double reservations, stale offer acceptance, incorrect deposit math, invented AI facts, and broken user journeys. Report concrete reproducible findings with file locations, severity, and suggested corrections. Do not propose a redesign or unrelated features.

## 11. 24-hour schedule

Hours are relative to coding kickoff. If less time remains, shorten scope rather than removing integration and demo preparation.

| Hours | Team milestone |
|---|---|
| 0-1.5 | Freeze scope, demo, schema, API contracts, ownership, and shared scaffold. Confirm event rules. |
| 1.5-3 | Deploy skeleton. Prove one Gemini call, email/auth path, database write, and image upload. |
| 3-7 | Each module builds its first slice. Person 3 uses fixtures that match the contract. |
| 7-10 | Integrate request -> match -> listing -> negotiated offer. |
| 10-14 | Complete sale and loan pickup. Integrate simulated collateral and reservation checks. |
| 14-17 | Loan return, photos, structured reviews, public requests. Person 2 helps Person 4. |
| 17-20 | Feature freeze. Two-user testing, permission checks, UI refinement, deployment fixes. |
| 20-22 | Rehearse, capture backup demo video, prepare submission and screenshots. |
| 22-24 | Final deployed checks and submission buffer. No architectural changes. |

Checkpoint: by hour 10, two people must be interacting with the same persisted request/listing/exchange on the deployed app.

Cut order if behind:

1. External search, sponsor extras, live payment integration, and trade are already deferred.
2. Cut gamification, automated appraisal, advanced route optimization, and delayed review publication.
3. Cut price-history generation; retain a transparent missing-data state or labeled fixtures.
4. Simplify chat to messages plus refresh/polling.
5. Prioritize one complete borrowing demo plus a straightforward purchase path.
6. Preserve access control, honest simulation labels, core Gemini matching, readable UI, and demo time.

## 12. Frutiger Aero implementation brief

Use sky-blue and leaf-green accents, glossy highlights, rounded translucent frames, gentle water/bubble details, and soft environmental imagery. Place long text and form fields on sufficiently opaque surfaces. Use native-looking tactile buttons with visible focus and active states. Represent item circulation with a small completed-exchange animation. Support reduced motion; do not animate behind dense text. Do not add a heavy 3D engine for the aesthetic.

Design the same six components first: button, field, card, dialog, badge, and offer summary. Apply these consistently to both marketplace and exchange screens.

Sustainability story: reuse existing possessions, short-term access, local handoffs. Metrics: completed secondhand sales and loans, distinct items circulated. Avoid CO2 numbers or "purchases prevented" claims without actual supporting measurement.

## 13. Validation checklist

Business behavior:

- Buying does not require reputation history.
- Borrowing eligibility checks fee and deposit affordability separately.
- Lower deposit acknowledgment is required and tied to the current offer.
- Money rounding works and negative values are rejected.
- Price boundaries behave exactly as specified.
- Uncertain matching attributes are not presented as verified facts.
- Expired/unavailable listings do not appear as confirmed matches.
- Two acceptances cannot reserve an item twice.
- Offer changes reset acceptance.
- A sale cannot demand loan-return fields.
- A loan cannot complete without its return workflow.
- Duplicate clicks do not duplicate records.
- A cancellation cannot erase an outstanding loan.
- Disputed evidence does not automatically produce a financial penalty.

Access:

- Unverified/wrong-domain users cannot post or transact.
- A participant cannot alter the other person's acceptance or evidence.
- A third party cannot view chat or condition evidence.
- Browser code contains no secret API or service-role keys.
- Uploaded image type/size is validated and filenames are not trusted.
- User text is rendered as text, not executable HTML.

AI:

- Structured output is validated.
- Gemini errors produce an editable manual form, not fabricated success.
- Listing text is treated as data, not instructions.
- Real inference is used in the primary demo; saved output is disclosed as fallback.
- Fixture pricing/history is visibly distinct from real records.

UI/deployment:

- Run one sale and one loan with two separate browser sessions.
- Check empty, loading, rejected, and error states.
- Check phone and desktop layouts.
- Verify storage and records persist after deployment restart.
- Rehearse the exact demo on the deployed URL.

## 14. Demo and judging

Use a seeded suit listing and one intentionally incompatible listing, clearly described as demo inventory. Demonstrate:

1. A new user requests a suit using natural language.
2. Gemini extracts the fields and flags any missing size/date.
3. The system explains one match and one rejection.
4. The borrower proposes lower collateral; the lender sees the uncovered amount and accepts.
5. Both accept the current agreement and select a public meeting spot.
6. Show pickup evidence, handoff, return evidence, and structured review.
7. Briefly show no-match -> optional public request.

Suggested 3-minute split:

- 25 seconds: who has the problem and why reuse helps.
- 100 seconds: live request, matching, negotiation, and agreement.
- 30 seconds: prepared later-stage return/review screen; disclose the stage jump.
- 25 seconds: technical decisions, limitations, and future work.

Gemini contribution: language normalization, clarification, grounded matching explanations. Frutiger Aero contribution: coherent optimistic nature-inspired interface tied to circulation. Beginner contribution: explain what each teammate implemented and learned. Disclose coding-agent use according to event rules; do not assume a specific eligibility policy.

Honest limitations:

- Prototype payments and collateral are simulated.
- Lower collateral leaves risk with the consenting owner; reimbursement is not guaranteed.
- Price data is sparse; fixtures are labeled.
- Suggested locations do not guarantee safety.
- External marketplace search and live financial dispute handling are future work.

## 15. Official references checked for this plan

- Codex project instructions: https://developers.openai.com/codex/guides/agents-md/
- Codex worktrees: https://developers.openai.com/codex/app/worktrees/
- Claude Code memory and imports: https://code.claude.com/docs/en/memory
- Gemini structured output: https://ai.google.dev/gemini-api/docs/structured-output
- Supabase PostgreSQL: https://supabase.com/docs/guides/database/overview
- Supabase Python authenticated user lookup: https://supabase.com/docs/reference/python/auth-getuser
- Supabase email delivery limitations: https://supabase.com/docs/guides/auth/auth-smtp
- Supabase storage buckets: https://supabase.com/docs/guides/storage/buckets/fundamentals
- Stripe authorization deadlines: https://docs.stripe.com/payments/place-a-hold-on-a-payment-method
- Stripe payment disputes: https://docs.stripe.com/disputes/how-disputes-work
