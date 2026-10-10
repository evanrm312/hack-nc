"""Stub: normalize_request. Owned by Person 2.

Contract: docs/contracts.md -> "Person 2 function signatures".
The stub never calls Gemini and never invents extracted values. Every field
is unknown (null) and the response is labeled as a stub.
"""

from __future__ import annotations

from datetime import datetime


def normalize_request(text: str, now: datetime, timezone: str) -> dict:
    """Return a NormalizedRequest dict (see docs/contracts.md).

    Args:
        text: the user's original natural-language description.
        now: current time, timezone-aware UTC, used to resolve relative dates.
        timezone: IANA zone the user is in, e.g. "America/New_York".

    Returns:
        dict matching the NormalizedRequest schema. Unknown values are null.
        ``follow_up_questions`` lists what the user must confirm.
        ``source`` is "gemini", "manual", or "stub".
    """
    return {
        "source": "stub",
        "modes": None,
        "category": None,
        "required_specifications": {},
        "preferred_specifications": {},
        "budget_cents": None,
        "max_deposit_cents": None,
        "needed_by": None,
        "use_start": None,
        "use_end": None,
        "area": None,
        "ambiguous_dates": [],
        "follow_up_questions": [
            "Request normalization is not implemented yet (stub). "
            "Fill in the fields manually."
        ],
        "original_text": text,
    }
