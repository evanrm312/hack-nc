# Dimensional Campus Current redesign

Review branch: `ui/frutiger-aero-redesign`, based on main `9d778b5`.
No backend, seed, fixture, sample image, database, or API contract changes.
This is an original campus interface, not a Microsoft product.

## Inspected references → decisions

| Source | Actually inspected | Application |
|---|---|---|
| [Waterloo Computer Museum](https://uwaterloo.ca/computer-museum/exhibits/frutiger-aero-future-2000s) |2025 retrospective; exhibit collage shows foliage, water, glass window frames and opaque photo content. This is a modern historical interpretation, not an original2000s screenshot. |Real sky and sunlit leaves; greenery is the home side pane and forms/terms background. No invented environmental statistics. |
| [Microsoft desktop guidance](https://learn.microsoft.com/en-us/windows/win32/uxguide/winenv-desktop) |Annotated Windows7 aquatic desktop and access-point screenshots; work area above a bottom taskbar, Start at left, status area at right, raised active application. |Permanent bottom navigation with labeled links, original leaf orb launcher, active-page lighting, account access at right. Reserved bottom clearance. |
| [Microsoft taskbar article (2008)](https://blogs.windows.com/windowsexperience/2008/11/23/the-new-windows-taskbar-in-windows-7/) |Contemporary article describing quick access/application management and pinned destinations. |Every task has a real existing destination; launcher provides access on phone widths. No imitation task thumbnails or fake OS features. |
| [Windows7 illustrated chapter (2009)](https://download.microsoft.com/download/9/a/3/9a36304d-cb64-427e-a184-4ed1bb556712/win7_sbs_earlycontent_ch1.pdf) |Downloaded original61-page PDF; rendered PDF pages17 and20, showing desktop/taskbar and two-part Start menu (opaque destination list, translucent side pane). Browser research tool could not fetch its octet-stream, direct download succeeded. |Launcher destination list + green purpose pane. Window titlebar and internal location toolbar. No fake minimize/maximize/close controls. |

Reference images are kept outside the repository, not shipped as assets.
An attempted Wikimedia UNC Old Well download was blocked by429/403; it is not
used. The nature photos are not claimed to depict UNC.

## Baseline component audit → replacements

Baseline screenshots were captured from the unchanged main UI using Firefox
headless at 1440×1000, before edits, on isolated sandbox data. Every reachable
route in the review manifest was rendered. These are rendered screenshots,
not claims of an interactive manual walkthrough.

| Existing component | Replacement and visual reference | Interaction preserved |
|---|---|---|
|Header nav, tiny brand, separate animated bubbles |Compact brand/status header; fixed glass taskbar; original Start orb and disclosure launcher. Microsoft desktop/access-point screenshots. |Same URLs, account hook, browser history. Escape/outside/focus dismissal. |
|Large single-column request card |60/40 request/nature composition, framed photograph, request→match glass motifs; Waterloo nature/glass collage. |Text/photo upload, exact example values, normalization, required confirmation and request creation hooks. |
|Four repeated how-to cards |Connected process strip, four consistently lit circular SVG icons. |Describe→matches→agree→meet; honest simulation notice. |
|Floating catalogue cards |Explorer-like bounded list rows; inset thumbnails; green service row accent. Microsoft window content region hierarchy. |Original titles, prices, attributes, owner badges, links; photos never replaced. |
|Interpretation then long results stack |Editable interpretation pane beside results, with a shared request summary. |PATCH, confirmation blockers, match reasons, no-match publishing and privacy preview. |
|Long listing form |Details pane and green terms/availability pane; inset controls, grouped service or item terms. |Existing mode exclusivity, service fields, deposit acknowledgment guidance, upload and validation. |
|Listing details |Content panel beside terms/owner/meeting region. |Unknown stays unknown, simulated money labels, original disabled actions remain honest. |
|Public request feed |Compact green filter toolbar and list view. |Mode/area filters and sanitized public data only. |
|Sign-in + raw account JSON |Account window with nature/privacy pane; account information disclosure. |Shared auth initialization untouched; email/sandbox form, sign-out, error/session handling and account JSON hook. |
|Exchange cards/lifecycle before current offer |Negotiation and private conversation first; updated terms/history disclosures; separate physical lifecycle area below. | All IDs, forms, participants, offer revision acceptance and evidence hooks preserved. |
|Messages, dialogs, status/error/empty states |Inset message area, paper/green message surfaces, glass dialog frame, semantic opaque notices. |Native dialog focus behavior, private data, error text, loading and retry actions. |

## Materials, typography and assets

Light comes from upper left. Photography is the farthest layer; the window has
translucent blue chrome and bright rim; content is opaque enough to read; fields
are inset; action controls use narrow reflections and lower-edge shading.
Green means campus circulation and offering/terms areas, not measured impact.
No persistent decorative motion is added. Reduced-motion disables transitions.
The local licensed Source Sans3 humanist font is a modern substitute; Segoe UI
is a fallback. See [asset provenance](../static/assets/ASSETS.md).

## Review constraints and known baseline gaps

The computer-use tool reported no enabled browser surfaces. A temporary Firefox
WebDriver harness was subsequently installed **outside the repository**. It
performed actual local UI interactions and captured settled screenshots. These
are automated browser checks plus visual inspection of screenshots, not a manual
GUI walkthrough. Initial one-shot CLI renders used preloaded isolated API reads;
the final paired screenshots and functional journeys used the actual application
and sandbox sign-in form without those preloads or token injection.

All application reads/writes for QA targeted isolated local SQLite and local
Storage. No real auth tokens, email links, Gemini calls, shared database records,
or shared seed commands were used. The preview database is a copy of the isolated
records taken before mutation journeys, so it excludes the extra QA-created
listings/requests/messages. These local QA records are not changes to sample data
in main.

The baseline service exchange room does not render: `loadInitial()` unconditionally
GETs `/api/exchanges/{id}/evidence`, which services correctly reject with
`invalid_transition` ("Services have no handoff, evidence, or return step"). Even
without that call, `render()`/`fillDraft()` assume item-shaped participants,
condition/deposit fields and a non-null current offer; a newly created service
has no offer yet. Service room scheduling/completion UI requires Sid/Emily's
functional integration. The
redesign corrects the service display label only, not its API/payload behavior.
Existing marketplace "Start exchange" and public "I have this" controls remain
unfinished/disabled. Their behavior is not fabricated by this redesign.

## Verification actually run

| Check | Result | Scope |
|---|---|---|
| `python -m pytest -q` | 285 passed, 1 skipped, 1 existing Google SDK deprecation warning |Isolated SQLite per test; external Gemini/Supabase adapters mocked. Dedicated PostgreSQL catalog check skipped: `TEST_DATABASE_URL` not configured. |
| `node --test tests/browser_auth.test.cjs tests/browser_shell.test.cjs` | 10 passed, 0 failed, 0 skipped | 5 existing mocked auth lifecycle checks + 5 launcher/example DOM harness checks. |
| Temporary Firefox WebDriver layout/interaction pass | 87 assertions passed |12 before/after routes; exact 1440/1024/390 CSS-pixel viewports via BiDi; overflow, launcher Space/Tab/Escape/outside/focus, errors, example states, service visibility, native dialogs, keyboard focus/taskbar clearance, sandbox refresh/navigation/sign-out. |
| Temporary Firefox actual API journeys | 14 assertions passed |Photo normalization manual fallback; image-only text/mode blockers; no request before confirmation; one request created; $80 deposit blocker and its removal at $200; publish privacy dialog/public fields; service creation; new sale listing/local photo upload/public retrieval; private messages; offer disclosure. Writes only to isolated QA SQLite/Storage. |
| Final clean-preview checks | 5 assertions passed |Active request workspace task, long title at 390px, reduced-motion media/transition/menu behavior. |
| Settled dialog/confirmation checks | 14 assertions passed |Opaque settled dialogs inside viewport, action/footer clearance and restored focus at all 3 widths; full-width confirmation and 390px overflow. |
| JavaScript syntax | All 6 scripts pass `node --check` |api/auth/components/marketplace/exchanges/shell. |
| `git diff --check` | Passed |No whitespace errors. |
| Template hook audit | 7 affected page templates passed |Original IDs retained with no duplicates. |

Firefox total: **120 assertions passed** across the 4 temporary passes. Earlier
harness attempts exposed a minimum browser-window width and capture timing issues;
BiDi supplied exact 390px sizing, and final captures wait for fonts, APIs, focus/
caret placement and dialog transitions. Those initial artifacts were replaced.
The complete Python suite ran against this feature worktree based on `9d778b5`;
later edits were presentation-only and were checked with final browser renders,
syntax and whitespace checks.

**Unverified:** manual GUI walkthrough; real Supabase email/browser session;
live Gemini/Vision proposals; hosted Supabase Storage; physical pickup/return
journey in a real two-account session. Automated backend permission/lifecycle
coverage passes. The unsupported service room and disabled marketplace entry
buttons are existing integration gaps, not features invented for the redesign.
A browser without backdrop blur was not available; its opaque chrome fallback
is implemented but not tested in such a browser.

## Files and local review

Changed: shared `templates/base.html` and original SVG icon macro; home/results/
feed/listing form templates; account template; exchange templates/layout styles;
`theme.css` + `desktop.css`; UI-only marketplace grouping/source label and exchange
mode label; `shell.js`; launcher tests; this handoff and asset/license records.
`api.js`, `auth.js`, shared components logic, backend/contracts/models/migrations,
existing tests/fixtures/seed scripts and sample assets are untouched.

Preview is running at **http://localhost:5055/** from:
`/home/evan/Projects/hack-nc-aero-redesign`.
Use the sign-in page's **sandbox** Alice/Bob options. No email is sent. Gemini is
intentionally unset; normalization offers the real manual fallback. The copy of
local preview data is `/tmp/campus-aero-review/review-preview.sqlite3`, not the
shared database. Restart this session's preview with:

```bash
cd /home/evan/Projects/hack-nc-aero-redesign
PYTHONPATH=. /home/evan/Projects/hack-nc/.venv/bin/python /tmp/campus-aero-review/local-preview.py
```

Before/after images and the comparison gallery are outside git:
`/tmp/campus-aero-review/review.html`, `before/`, `after/`.
Reference snapshots are in `/tmp/campus-aero-review/references/`.
Temporary test scripts/results are in the same review directory, not application
code or added application dependencies. No UI changes were pushed, deployed,
merged, or committed to main. Explicit user approval is required before main.
