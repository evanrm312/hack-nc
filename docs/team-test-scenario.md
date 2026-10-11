# Campus Current team acceptance test

Run against https://hack-nc.onrender.com after the temporary email-confirmation change deploys. Allow 30–45
minutes. Use three password test accounts using UNC addresses in separate browser profiles:
**A borrower**, **B lender**, **C outsider**. Never share passwords or paste
access tokens into chat. Mark each row PASS/FAIL and record the page/record ID,
expected versus actual behavior, and a screenshot without emails or secrets.

This is a test to execute, not a claim that these exchanges already happened.
The imported demo owners cannot sign in or answer messages. Use a new listing
owned by B for the full exchange. Keep it clearly labeled QA inventory.

## 1. Password onboarding and repeat sign-in

Existing accounts: enter your UNC email on Sign in, select **Forgot password /
first password**, and open the newest recovery email once. Choose and repeat
an 8+ character password in **Set your password**, then Save password.
If already signed in, open Account and set your password directly.

New accounts: **New here? Create an account**, enter a UNC address, choose and
repeat a password. Temporary testing mode signs you in immediately without an
email. Expect **Test account (email not verified)**, not a verification claim.
Use fresh accounts for A/B/C to avoid recovery email limits. Existing accounts
with passwords can sign in normally; recovery still requires an email.
Ordinary password sign-in sends no email.

| Check | Expected |
| --- | --- |
| Sign out; sign in with email/password three times | Each succeeds without an inbox link; no `/otp` or `/recover` call on normal login |
| Try an incorrect password once | Clear retry message; no authenticated account |
| Try `someone@unc.edu.evil.com` | Rejected before provider call; never verified |
| Create a fresh test account | Immediate session; “Test account (email not verified)”; `/api/me` 200; no inbox link |
| Existing verified account signs in | Original profile and records preserved |
| Refresh, open My Exchanges, and use `/sign-in?next=%2Fexchanges` | Session persists; internal destination opens |
| Sign out, refresh | Browsing works; `/api/me` 401; posting requires sign-in |

Optional developer check: in Network inspect status/path only. Do not copy
Authorization headers, request passwords, callback fragments or response tokens.

## 2. Public catalog and licensed photos

Browse Home while signed out. Expect the 52 imported public demo listings plus
the two preserved originals (54 immediately after repair; team-created listings
will increase this count). Demo cards and owners must be labeled. Open a suit,
an electronics item and a service. Each imported photo loads; description
credits identify the licensed illustrative image. A reference photo never
establishes the actual listed item's size, model, condition or accessories.

No console/network 500s from `/api/listings` or `/api/recommendations`;
`/api/ready` returns 200. Unknown attributes stay unknown; free rental fee is
separate from a possible deposit. Check desktop and a 390px phone viewport.

## 3. Gemini review, calendar and manual editing

Sign in as A. Enter:

> I want to borrow a navy suit with a 40R jacket for an interview next Tuesday.
> My rental budget is $20 and I can afford a $60 deposit. I don't know the
> trouser size or the pickup time yet.

Select **Interpret my request**. The date of “next Tuesday” varies with the
run date: inspect it instead of assuming a fixed calendar day.

| Check | Expected |
| --- | --- |
| Review opens | Editable details, no Gemini follow-up warning list; nothing saved yet |
| Mode/category/specifications | Borrow/formalwear/40R are sensible proposals; edit any incorrect proposal |
| Money | Rental budget $20 = 2000 cents; max deposit $60 = 6000 cents; amounts remain separate |
| Missing details | Trouser size and omitted dates/times are blank/unknown, not invented |
| Ambiguous date | Calendar cards show explicit Eastern dates; edit or clear a date |
| Change a date after selecting “This schedule works for me” | Schedule acknowledgement clears and cards update |
| Find matches without reviewing the proposed schedule | Stay on review; one helpful inline schedule prompt |
| Acknowledge and Find matches | One private request is saved; results use your edited terms |
| Edit details on results | Update results uses those terms and preserves unknowns |

Repeat with a photo of an item you own, or a clearly identified licensed
reference image. Photo attributes need **Accept** or **Dismiss** and remain
editable; image-only input still requires your description and buy/borrow
choice. No size, condition, price, model or verification is inferred from the
photo. The reference upload is private and is not stored.

Optional fallback check, only in a local preview: simulate unavailable Gemini.
The editable manual form still opens without provider debug/error text.
Do not break production keys or disable the provider to test fallback.

## 4. Controlled listing and matching

B creates **QA suit — TEST ONLY — YYYY-MM-DD**, with a test image and description
“Team acceptance test; not an actual public offer.” Use:

| Field | Value |
| --- | --- |
| Category/mode | Formalwear; borrow only |
| Required specification | `jacket_size = 40R` |
| Preferred specification | `color = navy` |
| Rental fee | $20 |
| Proposed item value | $200 |
| Initial deposit proposal | 100% = $200 |
| Availability | Explicit future test dates covering A's edited borrowing interval |
| Meeting spot | One existing public campus meeting spot |

Uploading/validating the photo publishes the listing. Refresh My Listings:
it persists. As A, search the same 40R need with a $60 deposit limit. The
$200 deposit must not be shown as an affordable confirmed offer; the listing
may be excluded or marked for negotiation. Missing required compatibility is
“needs confirmation.” Try a 38S requirement: never a confirmed size match.
Open B's listing directly to negotiate as A.

## 5. Negotiation, agreement and privacy

A starts a private conversation about B's QA listing. Send one clearly marked
QA message. B sees it and receives a notification. C sees no private room,
message or precise meeting details when opening the copied exchange URL.

B proposes a $20 fee, $200 agreed item value, and 30% collateral. Expect a
**$60 deposit and $140 uncovered value**, with the label **Simulated: no real
funds are reserved or charged**. B must explicitly acknowledge the uncovered
value before accepting. A and B select the same future pickup/return dates
and public meeting spot.

1. A accepts the current version.
2. B edits the fee to $15 (1500 cents). Both acceptances reset.
3. A refreshes and confirms the new $15 fee, $60 deposit, $200 value.
4. Both accept the exact new revision; B acknowledges the uncovered amount.
5. The exchange becomes reserved; the QA item has one active reservation.
6. C cannot reserve the same item through another competing agreement.

Optional developer check: a stale acceptance returns 409 and does not reserve.
An anonymous protected request returns 401; authenticated nonparticipants cannot
read messages/evidence. Record status only, never private contents/tokens.

## 6. Pickup, return and reviews

Before uploading condition evidence, try confirming pickup: missing evidence
blocks the action. Upload clearly labeled test condition photos. Both A and B
review them and confirm possession/condition. One confirmation alone leaves
the item reserved; both advance the loan to **on_loan**. Photos lock after the
first confirmation. C cannot retrieve the copied evidence URL (401/403 as
appropriate), and it must not be a public Storage object.

A uploads **pre_return** evidence and initiates return. The loan moves to
**return_pending**. B uploads **post_return** evidence. Both review the photos
and accept condition/return. One acceptance alone does not complete the loan;
both yield **completed**, and the listing becomes available again.

Only completed participants can submit one review each. Third parties and
pre-completion reviews are rejected. Ratings/history reflect only this actual
test exchange; there were no pre-populated reviews. Confirm the simulated
deposit label throughout: no funds are held or charged.

## 7. Cancellation, dispute and public-request privacy

Use separate clearly labeled QA exchanges for these optional paths:

- Cancel before agreement; no reservation remains. A reserved cancellation
  releases the listing according to the current workflow.
- On a separate loan, initiate return then report a test issue. It becomes
  disputed, retains its reservation, and never automatically charges anyone.
- Publish a separate unmet request through its preview. Public feed shows only
  permitted fields, without precise schedules, email or private messages.
  Close/cancel the request after inspection.
- If the team uses club listings, verify outsiders cannot see club listings or
  their photos and members retain access. Use an existing test club rather than
  altering memberships solely for this core test.

## Finish and record results

Withdraw B's QA listing when testing finishes and cancel unused QA requests or
negotiations. Leave completed test history truthful and labeled; do not delete
shared production records or restore a database to erase QA history. A disputed
QA exchange stays visibly flagged for operator follow-up rather than silently
completing it. Sign out each account and confirm public browsing still works.

Record: deployment commit, test date, browser/viewport, each PASS/FAIL, created
listing/request/exchange IDs, and unresolved issues. Final release acceptance:
readiness/catalog/recommendations 200, normal password login sends no email,
Gemini proposals remain editable, calendar acknowledgement works, records survive
refresh, and private state is denied to nonparticipants.
