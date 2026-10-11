"""MeetingSpot: public campus handoff locations (seeded, read-only for users)."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, JSON, String, Text
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

    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    coordinate_source: Mapped[str | None] = mapped_column(Text)
    safety_attributes: Mapped[dict | None] = mapped_column(JSON)
    safety_source: Mapped[str | None] = mapped_column(Text)
    safety_checked_at: Mapped[str | None] = mapped_column(String(10))

    def to_dict(self) -> dict:
        from ..meeting_sources import reference_for
        result = {
            "id": self.id,
            "label": self.label,
            "public_area": self.public_area,
            "access_notes": self.access_notes,
            "safety_attributes": {key: (self.safety_attributes or {}).get(key) for key in
                ("lighting", "cameras", "staffing", "public_access", "opening_hours")},
            "safety_source": self.safety_source,
            "safety_checked_at": self.safety_checked_at,
        }

        result.update(reference_for(self.label))
        if self.latitude is not None and self.longitude is not None and self.coordinate_source:
            result.update(latitude=self.latitude,longitude=self.longitude,coordinate_source=self.coordinate_source,
                          coordinate_description="Catalog coordinates")
        return result
