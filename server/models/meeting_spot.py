"""MeetingSpot: public campus handoff locations (seeded, read-only for users)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from ..db import db, new_id, utcnow


class MeetingSpot(db.Model):
    __tablename__ = "meeting_spots"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    public_area: Mapped[str] = mapped_column(String(80), nullable=False)
    access_notes: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "label": self.label,
            "public_area": self.public_area,
            "access_notes": self.access_notes,
        }
