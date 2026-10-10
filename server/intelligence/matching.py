"""Stub: match_listings. Owned by Person 2.

Contract: docs/contracts.md -> "Person 2 function signatures".
The stub performs no real compatibility checks. It returns every listing it is
given as "needs_confirmation" with an explicit stub reason so that nothing is
presented as a verified match. It never fabricates listing ids.
"""

from __future__ import annotations


def match_listings(request: dict, listings: list[dict]) -> dict:
    """Return MatchResult (see docs/contracts.md).

    Args:
        request: a NeedRequest dict as returned by GET /api/requests/{id}
            (owner view), including ``normalized``.
        listings: current Listing dicts with status "available".

    Returns:
        {"confirmed": [MatchEntry], "needs_confirmation": [MatchEntry],
         "rejected": [MatchEntry], "source": "deterministic"|"stub"}
        Every MatchEntry.listing_id must be the id of one of ``listings``.
    """
    needs_confirmation = []
    for listing in listings:
        needs_confirmation.append(
            {
                "listing_id": listing["id"],
                "mode": None,
                "score": None,
                "reasons": [],
                "shortcomings": [
                    "Matching is not implemented yet (stub); "
                    "compatibility has not been checked."
                ],
                "unknown_required": [],
            }
        )
    return {
        "source": "stub",
        "confirmed": [],
        "needs_confirmation": needs_confirmation,
        "rejected": [],
    }
