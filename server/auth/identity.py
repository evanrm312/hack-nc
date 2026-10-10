"""Verified identity resolution.

A request proves who it is with ``Authorization: Bearer <token>``.

- AUTH_MODE=supabase: the token is a Supabase access token. We ask Supabase
  Auth (GET /auth/v1/user) who it belongs to and whether the email is
  confirmed (``email_confirmed_at``). Nothing is trusted from the browser.
- AUTH_MODE=sandbox: the token is ``sandbox:<email>``. Only emails listed in
  SANDBOX_USERS resolve. Profiles created this way are labeled
  ``verification_source="sandbox"`` and ``is_demo=True`` so the UI can show
  that they did not complete real verification.

The allowed-domain check is exact after normalization (lowercase, text after
the last "@"), never a suffix match.
"""

from __future__ import annotations

import hashlib
import json
import urllib.error
import urllib.request
from dataclasses import dataclass


class AuthUnavailable(Exception):
    """The auth provider could not be reached or returned garbage."""


@dataclass(frozen=True)
class Identity:
    subject: str  # opaque provider id, stored as Profile.auth_subject
    email: str  # normalized; used only for the domain check, never stored on Profile
    email_confirmed: bool
    source: str  # "supabase" | "sandbox"

    @property
    def domain(self) -> str | None:
        return email_domain(self.email)


def normalize_email(email: str) -> str:
    return email.strip().lower()


def email_domain(email: str | None) -> str | None:
    if not email or "@" not in email:
        return None
    return normalize_email(email).rsplit("@", 1)[1]


def domain_allowed(email: str | None, allowed_domain: str) -> bool:
    """Exact normalized comparison. 'x@unc.edu.evil.com' is NOT allowed."""
    domain = email_domain(email)
    return domain is not None and domain == allowed_domain.strip().lower()


def bearer_token(header_value: str | None) -> str | None:
    if not header_value:
        return None
    scheme, _, token = header_value.strip().partition(" ")
    if scheme.lower() != "bearer" or not token.strip():
        return None
    return token.strip()


def resolve_identity(token: str | None, config) -> Identity | None:
    """Map a bearer token to an Identity, or None if it does not resolve."""
    if not token:
        return None
    mode = config["AUTH_MODE"]
    if mode == "sandbox":
        return _resolve_sandbox(token, config)
    if mode == "supabase":
        return _resolve_supabase(token, config)
    raise RuntimeError(f"Unknown AUTH_MODE {mode!r}")


def _resolve_sandbox(token: str, config) -> Identity | None:
    prefix = "sandbox:"
    if not token.startswith(prefix):
        return None
    email = normalize_email(token[len(prefix):])
    if email not in set(config["SANDBOX_USERS"]):
        return None
    digest = hashlib.sha256(email.encode("utf-8")).hexdigest()[:24]
    return Identity(
        subject=f"sandbox:{digest}",
        email=email,
        email_confirmed=True,  # by definition of the labeled sandbox
        source="sandbox",
    )


def _resolve_supabase(token: str, config) -> Identity | None:
    url = config["SUPABASE_URL"].rstrip("/") + "/auth/v1/user"
    req = urllib.request.Request(
        url,
        headers={
            "apikey": config["SUPABASE_ANON_KEY"],
            "Authorization": f"Bearer {token}",
            "Accept": "application/json",
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=config["AUTH_HTTP_TIMEOUT_SECONDS"]) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        if err.code in (400, 401, 403):
            return None  # invalid or expired token
        raise AuthUnavailable(f"Supabase auth returned HTTP {err.code}") from err
    except (urllib.error.URLError, TimeoutError, ValueError) as err:
        raise AuthUnavailable(str(err)) from err

    subject = payload.get("id")
    email = payload.get("email")
    if not subject or not email:
        return None
    return Identity(
        subject=f"supabase:{subject}",
        email=normalize_email(email),
        email_confirmed=bool(payload.get("email_confirmed_at")),
        source="supabase",
    )
