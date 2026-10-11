# Aarush → Evan: ratings and levels integration contract

No ratings/levels branch or handoff is present in the fetched remote branches
as of October 11, 2026. `p2-intelligence` has one unpublished-to-main Gemini
fallback commit (`21d1212`), not a levels implementation. Intelligence files,
Review, Profile and review routes have not been changed by this follow-up.
Evan should forward this contract; no teammate messages were sent automatically.

## Existing interface to preserve

- `POST /api/exchanges/{id}/review`: verified participant, completed exchange,
  integer stars 1–5, structured answers and optional comment ≤2000 characters.
- Unique `(exchange_id, reviewer_id)`; other participant is derived server-side.
- `GET /api/exchanges` already supplies `my_review` and `can_review`.
- Existing creation forbids self-exchanges, but the review route should also
  explicitly reject identical reviewer/reviewee IDs before awarding points.
- Existing service review handling needs Aarush's review: the shared route
  currently only forces `returned_on_time=not_applicable` for sales. Services
  must also use not-applicable item/return questions, not imply condition evidence.

## Proposed small extension — pending Aarush agreement

Keep review writes on the existing endpoint. Expose server-computed
`rating_summary: {count, average_stars}` and
`level: {number, points, policy_version}` as additive profile fields, with no
client-writable equivalents. Public summaries contain no exchange IDs, comments,
locations or private history. No display claiming trust, safety or verification.

A unique server ledger key per eligible completed exchange/recipient prevents
point farming. Review retries never award points twice; users cannot review
themselves, unrelated or incomplete exchanges. Define completed service eligibility
and a fixed, modest level policy before UI integration. Levels never affect
collateral, budgets, matching eligibility, purchase caps or verification badges.

Disputed outcomes award no completion points. Define reversal as an auditable,
server-authorized negative ledger adjustment referencing the original award;
no new exchange status or automatic charge is proposed here. A retry of the
same reversal must be a no-op. Keep seeded identities visibly demo/sandbox.

For rating notifications, emit `review_received` only for the reviewee after a
committed eligible review; key `review:{review_id}`. Level events may be shown to
the recipient only after agreement on the actor/self-notification exception.
Do not add either event until Aarush confirms the policy and additive fields.

## Migration handoff

Current intended head is `c707browserroles`. Rebase new migrations onto it after
this PR is reviewed; never rewrite applied revisions. New tables must revoke
`anon`, `authenticated` and `PUBLIC` access and enable RLS without client policies:
Flask's server DB role provides authorization. Its migration role must bypass
RLS. If Aarush already has another migration head, Evan should reconcile the
chain explicitly before applying it. Publish the branch and eligibility/point
policy so Evan can integrate UI and run combined checks.

## Existing intelligence gap observed

`server/intelligence/pricing.py:evaluate_price` still always returns
`insufficient_data` with `stub: true`; `tests/test_pricing.py` has no tests.
Item offers explicitly reject `price_reference_id` and `pricing_range_version`
with “price-reference integration is not available yet” in
`server/exchanges/routes.py`. No price appraisal or comparable-price enforcement
is implemented or claimed by this follow-up. Aarush owns the evaluator and
boundary tests; Evan owns wiring the reviewed contract into item offers when
available. Preserve honest unknown-price behavior until then.
