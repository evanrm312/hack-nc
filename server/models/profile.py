"""Profile: one row per verified identity.

The email address itself is never stored on the profile and never serialized.
``auth_subject`` is the opaque identity from the auth provider (Supabase user
id, or "sandbox:<email>" in sandbox mode).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import db, iso_utc, new_id, utcnow

VERIFICATION_SOURCES = ("supabase", "sandbox")


class Profile(db.Model):
    __tablename__ = "profiles"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    confirmed_email_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    # "supabase" = real email confirmation; "sandbox" = labeled demo identity.
    verification_source: Mapped[str] = mapped_column(String(16), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    @property
    def badge(self) -> str:
        if self.verification_source == "supabase":
            return "UNC email verified"
        return "Sandbox identity (not verified)"

    def to_public_dict(self) -> dict:
        """What other users may see. Never includes the email."""
        return {
            "id": self.id,
            "display_name": self.display_name,
            "confirmed_email_domain": self.confirmed_email_domain,
            "verification_source": self.verification_source,
            "badge": self.badge,
            "is_demo": self.is_demo,
        }

    def to_me_dict(self) -> dict:
        data = self.to_public_dict()
        data["created_at"] = iso_utc(self.created_at)
        return data
