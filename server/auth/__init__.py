"""Verified-identity helpers. Owned by Person 1; consumed by Persons 3 and 4.

    from server.auth import require_verified_user, optional_user, current_profile
"""

from .decorators import current_identity, current_profile, optional_user, require_verified_user
from .identity import Identity, domain_allowed, email_domain, normalize_email

__all__ = [
    "Identity",
    "current_identity",
    "current_profile",
    "domain_allowed",
    "email_domain",
    "normalize_email",
    "optional_user",
    "require_verified_user",
]
