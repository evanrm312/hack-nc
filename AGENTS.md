# Campus Current

Read BUILD_BRIEF.md and docs/contracts.md before implementation.

Read your assigned task in docs/tasks.md. Work only on that task.

## Product constraints

- Build the confirmed buy/borrow campus exchange scope.
- Gemini extracts and explains; Python enforces constraints and permissions.
- Unknown item attributes remain unknown.
- All money is integer USD cents; distinguish fee, value, and deposit.
- Low collateral requires explicit lender acknowledgment.
- No reputation-based purchase cap or automatic collateral discount.
- Payments/deposits are simulated and visibly labeled.
- Never invent transactions, ratings, verification, price evidence, or impact.
- Changed offer terms invalidate both acceptances.
- Private messages and evidence are accessible only to participants.
- A dispute never automatically triggers a charge.

## Collaboration

- Use your assigned branch and file ownership boundaries.
- Person 1 owns shared models, migrations, dependencies, and contracts.
- Propose shared changes to Person 1 instead of editing them concurrently.
- Do not overwrite another person's work or force-push shared branches.
- Keep changes small; avoid unrelated refactors and new frameworks.
- Do not add services, sponsor integrations, or nested agents without team assignment.

## Validation and handoff

- Run the relevant existing tests for your changes.
- Test permissions and invalid state transitions where applicable.
- For UI changes, check the affected journey in the browser.
- Never claim a check passed unless it ran.
- End with changed files, behavior, checks, and remaining blockers.
- Read README.md for the actual setup and run commands.
