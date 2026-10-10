"""Stub: evaluate_price. Owned by Person 2 (after matching works).

Contract: docs/contracts.md -> "Person 2 function signatures".
Rule to implement (BUILD_BRIEF.md section 4), all integer cents:
    block  if price > upper
    block  if 2 * price <= lower
    warn   if lower > price > lower / 2
    allow  if lower <= price <= upper
Free loans (price == 0 for a rental) are a separate explicit case.
If ``reference`` is None return verdict "insufficient_data".
"""

from __future__ import annotations


def evaluate_price(price_cents: int, reference: dict | None) -> dict:
    """Return PriceVerdict (see docs/contracts.md).

    Args:
        price_cents: the proposed sale price or rental fee, integer cents.
        reference: a PriceReference dict (lower_cents, upper_cents, version,
            price_type, duration_basis, is_fixture) or None.

    Returns:
        {"verdict": "allow"|"warn"|"block"|"insufficient_data",
         "reason": str, "reference_version": int|None, "stub": bool}
    """
    return {
        "verdict": "insufficient_data",
        "reason": "Price evaluation is not implemented yet (stub).",
        "reference_version": reference.get("version") if reference else None,
        "stub": True,
    }
