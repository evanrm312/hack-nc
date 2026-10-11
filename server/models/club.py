"""Seeded communities; join secrets are hashed and never serialized."""
from sqlalchemy import CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship
from ..db import db, new_id, utcnow


class Club(db.Model):
    __tablename__ = "clubs"
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    code_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_demo: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    def to_dict(self):
        return {"id": self.id, "slug": self.slug, "name": self.name, "is_demo": self.is_demo}


class ClubMembership(db.Model):
    __tablename__ = "club_memberships"
    __table_args__ = (
        UniqueConstraint("club_id", "profile_id", name="uq_club_membership"),
        CheckConstraint("role IN ('member', 'manager')", name="ck_club_member_role"),
    )
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    club_id: Mapped[str] = mapped_column(ForeignKey("clubs.id"), nullable=False, index=True)
    profile_id: Mapped[str] = mapped_column(ForeignKey("profiles.id"), nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="member")
    created_at = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    club = relationship("Club", lazy="joined")
