"""Profile: one row per verified identity.

The email address itself is never stored on the profile and never serialized.
``auth_subject`` is the opaque identity from the auth provider (Supabase user
id, or "sandbox:<email>" in sandbox mode).
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, String, Integer, CheckConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import db, iso_utc, new_id, utcnow

VERIFICATION_SOURCES = ("supabase", "supabase_test", "sandbox")


class Profile(db.Model):
    __tablename__ = "profiles"

    __table_args__ = (CheckConstraint("graduation_year IS NULL OR graduation_year BETWEEN 1900 AND 2200", name="ck_profile_graduation_year"),)
    avatar_path: Mapped[str | None] = mapped_column(String(255))
    bio: Mapped[str | None] = mapped_column(String(300))
    graduation_year: Mapped[int | None] = mapped_column(Integer)
    show_transaction_history: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=db.false())

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    auth_subject: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    display_name: Mapped[str] = mapped_column(String(80), nullable=False)
    confirmed_email_domain: Mapped[str] = mapped_column(String(255), nullable=False)
    # "supabase_test" = password account admitted without inbox verification.
    # "supabase" = real email confirmation; "sandbox" = labeled demo identity.
    verification_source: Mapped[str] = mapped_column(String(16), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    preferred_meeting_spot_id: Mapped[str | None] = mapped_column(ForeignKey("meeting_spots.id"))

    @property
    def badge(self) -> str:
        if self.verification_source == "supabase_test":
            return "Test account (email not verified)"
        if self.verification_source == "supabase":
            return "UNC email verified"
        return "Sandbox identity (not verified)"

    def to_public_dict(self) -> dict:
        """What other users may see. Never includes the email."""
        return {
            "avatar_url": f"/media/public/{self.avatar_path}" if self.avatar_path else None,
            "bio": self.bio,
            "graduation_year": self.graduation_year,
            "clubs": self.public_clubs(),
            "id": self.id,
            "display_name": self.display_name,
            "confirmed_email_domain": self.confirmed_email_domain,
            "verification_source": self.verification_source,
            "badge": self.badge,
            "is_demo": self.is_demo,
        }

    def public_clubs(self):
        from .club import ClubMembership
        rows = db.session.scalars(db.select(ClubMembership).where(ClubMembership.profile_id == self.id).order_by(ClubMembership.created_at, ClubMembership.id)).all()
        return [{"club": row.club.to_dict(), "role": row.role} for row in rows]

    def to_me_dict(self) -> dict:
        data = self.to_public_dict()
        data["preferred_meeting_spot_id"] = self.preferred_meeting_spot_id
        data["show_transaction_history"] = self.show_transaction_history
        data["created_at"] = iso_utc(self.created_at)
        return data
