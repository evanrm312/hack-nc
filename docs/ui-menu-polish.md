# Aero menu polish

Branch: `ui-aero-menu-polish`, continuing `c895344` and reconciled with
`origin/main` at `58d724e`. The PR includes the earlier unpublished Aero
redesign plus this refinement.

- Title Case taskbar, launcher, navigation titles, and Sign In.
- Shorter form, sidebar, and launcher copy; removed the repeated window brand.
- Contact shadows on account chrome, toolbar, image frames, and hovered links.
- Main's request-to-exchange links, listing photos/placeholders, item/service
  filters, and cancellation markup retained during conflict resolution.
- No backend, migrations, seeds, fixtures, or sample changes relative to main.

Verification for this commit:

- 13 Node browser auth/shell/discovery tests passed.
- 29 desktop Firefox checks passed at 1440px and 1024px: labels, real
  destinations, menu focus/Escape, shadows, layout, item/service controls,
  unique exchange IDs, private room rendering, sandbox refresh and sign-out.
- Seven JavaScript syntax checks and `git diff --check` passed.
- Python tests and mobile checks skipped as requested. No live Supabase auth
  or Gemini check; no shared database writes or reseeding.

Preview: `http://127.0.0.1:5057` (isolated local SQLite).
Desktop screenshots: `/tmp/campus-aero-menu-polish/`.
Main was not changed or deployed. Existing backend integration limitations
are outside this visual refinement.
