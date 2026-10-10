"""Person 2: Gemini normalization, matching, and pricing.

Owned by Person 2 (branch: p2-intelligence). Person 1 only created the stub
signatures below so the HTTP routes can import them. Replace the bodies; keep
the signatures and the documented return shapes in docs/contracts.md.
"""

from .matching import match_listings
from .normalize import normalize_request
from .pricing import evaluate_price

__all__ = ["normalize_request", "match_listings", "evaluate_price"]
