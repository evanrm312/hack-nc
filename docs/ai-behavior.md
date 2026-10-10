# AI behavior (Person 2)

Owned by Person 2 (branch `p2-intelligence`). Stub created by Person 1.

Document here:

- The Gemini structured-output schema used by `normalize_request` and how the
  server validates it with Pydantic before anything is stored.
- How unknown values stay `null` and how required vs preferred specifications
  are separated.
- Follow-up question policy, including ambiguous dates such as "2 a.m."
  resolved in America/New_York and confirmed by the user.
- Gemini timeout and API-failure behavior: an editable manual form, never a
  fabricated success.
- How listing text is treated as data, not instructions.
- How match explanations are grounded in real listing fields only.
