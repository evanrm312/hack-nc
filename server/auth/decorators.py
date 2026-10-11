"""Request-level auth helpers used by every protected endpoint.

    from server.auth import require_verified_user, current_profile

    @bp.post("/api/things")
    @require_verified_user
    def create_thing():
        owner = current_profile()   # a Profile row, never a client-provided id

Rules enforced here (BUILD_BRIEF.md section 3A / 8):
- 401 auth_required      no or unparseable bearer token
- 401 invalid_token      token did not resolve to an identity
- 403 email_not_confirmed provider says the email is not confirmed
- 403 domain_not_allowed  exact domain is not ALLOWED_EMAIL_DOMAIN
- 503 auth_unavailable   provider unreachable
"""

from __future__ import annotations

from functools import wraps

from flask import current_app, request
from sqlalchemy.exc import IntegrityError

from ..db import db
from ..errors import ApiError
from ..models import Profile
from .identity import AuthUnavailable, Identity, bearer_token, domain_allowed, resolve_identity

_SENTINEL = object()

# Per-request cache lives on the WSGI environ, not on ``g``: tests that keep
# one app context open across several test-client requests would otherwise
# leak one caller's identity into the next request.
_IDENTITY_KEY = "campus.identity"
_IDENTITY_ERROR_KEY = "campus.identity_error"
_PROFILE_KEY = "campus.profile"


def _cache() -> dict:
    return request.environ


def _load_identity() -> Identity | None:
    """Resolve and cache the caller's identity for this request (may be None)."""
    cache = _cache()
    if _IDENTITY_KEY in cache:
        return cache[_IDENTITY_KEY]
    token = bearer_token(request.headers.get("Authorization"))
    if token is None:
        cache[_IDENTITY_KEY] = None
        cache[_IDENTITY_ERROR_KEY] = ApiError(401, "auth_required", "Sign in to continue")
        return None
    try:
        identity = resolve_identity(token, current_app.config)
    except AuthUnavailable as err:
        current_app.logger.warning("Auth provider unavailable: %s", err)
        cache[_IDENTITY_KEY] = None
        cache[_IDENTITY_ERROR_KEY] = ApiError(503, "auth_unavailable", "Sign-in service is unavailable; try again")
        return None
    cache[_IDENTITY_KEY] = identity
    cache[_IDENTITY_ERROR_KEY] = (
        None if identity else ApiError(401, "invalid_token", "Session is invalid or expired")
    )
    return identity


def _verify(identity: Identity) -> None:
    confirmation_required = current_app.config["REQUIRE_EMAIL_CONFIRMATION"]
    if confirmation_required and not identity.email_confirmed:
        raise ApiError(403, "email_not_confirmed", "Confirm your email before posting or transacting")
    if not domain_allowed(identity.email, current_app.config["ALLOWED_EMAIL_DOMAIN"]):
        raise ApiError(
            403,
            "domain_not_allowed",
            f"An @{current_app.config['ALLOWED_EMAIL_DOMAIN']} email is required",
        )
    if confirmation_required and identity.source == "supabase":
        # Supabase auto-confirms signups when confirmation is disabled. That
        # timestamp is not evidence of inbox ownership when testing ends.
        profile = db.session.scalar(db.select(Profile).where(Profile.auth_subject == identity.subject))
        if profile is not None and profile.verification_source == "supabase_test":
            raise ApiError(403, "email_not_confirmed", "This test account needs email verification before use outside testing")


def _get_or_create_profile(identity: Identity) -> Profile:
    profile = db.session.scalar(db.select(Profile).where(Profile.auth_subject == identity.subject))
    if profile is None:
        source = identity.source
        if source == "supabase" and not current_app.config["REQUIRE_EMAIL_CONFIRMATION"]:
            source = "supabase_test"
        profile = Profile(
            auth_subject=identity.subject,
            display_name="",  # set below once the id exists
            confirmed_email_domain="" if source == "supabase_test" else identity.domain or "",
            verification_source=source,
            is_demo=source != "supabase",
        )
        db.session.add(profile)
        try:
            db.session.flush()
            # Neutral default; never derived from the email address.
            profile.display_name = f"Member {profile.id[:6]}"
            db.session.commit()
        except IntegrityError:
            # Initial page requests may resolve the same new identity together.
            db.session.rollback()
            profile = db.session.scalar(
                db.select(Profile).where(Profile.auth_subject == identity.subject)
            )
            if profile is None:
                raise
    return profile


def current_identity() -> Identity | None:
    return _load_identity()


def current_profile() -> Profile | None:
    """The verified caller's Profile, or None for anonymous/unverified callers.

    Does not raise. Use inside endpoints wrapped with ``require_verified_user``
    (always returns a Profile there) or with ``optional_user`` (may be None).
    """
    cache = _cache()
    if _PROFILE_KEY in cache:
        return cache[_PROFILE_KEY]
    identity = _load_identity()
    if identity is None:
        cache[_PROFILE_KEY] = None
        return None
    try:
        _verify(identity)
    except ApiError:
        cache[_PROFILE_KEY] = None
        return None
    cache[_PROFILE_KEY] = _get_or_create_profile(identity)
    return cache[_PROFILE_KEY]


def require_verified_user(view):
    """Reject the request unless the caller is a confirmed, allowed-domain user."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        identity = _load_identity()
        if identity is None:
            raise _cache()[_IDENTITY_ERROR_KEY]
        _verify(identity)
        _cache()[_PROFILE_KEY] = _get_or_create_profile(identity)
        return view(*args, **kwargs)

    return wrapper


def optional_user(view):
    """Public endpoint that may personalize for a verified caller (never 401s)."""

    @wraps(view)
    def wrapper(*args, **kwargs):
        current_profile()
        return view(*args, **kwargs)

    return wrapper
