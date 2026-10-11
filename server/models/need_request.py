"""NeedRequest: what a user is looking for.

Two serializations exist: the owner view (everything) and the sanitized
public view (no precise schedules, no pickup windows, no requester identity
beyond a display name). Precise times and contact details stay private.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint, JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import db, iso_utc, new_id, utcnow

REQUEST_VISIBILITIES = ("private", "public")
REQUEST_STATUSES = ("draft", "open", "fulfilled", "cancelled", "expired")


class NeedRequest(db.Model):
    __tablename__ = "need_requests"

    __table_args__ = (UniqueConstraint("requester_id","creation_key",name="uq_need_requests_creation"),)
    creation_key: Mapped[str | None] = mapped_column(String(80))
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    requester_id: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False, index=True)

    original_text: Mapped[str] = mapped_column(Text, nullable=False)
    # NormalizedRequest dict from docs/contracts.md (editable by the user).
    normalized: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    modes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)  # sale, borrow, or service

    budget_cents: Mapped[int | None] = mapped_column(Integer)
    max_deposit_cents: Mapped[int | None] = mapped_column(Integer)

    needed_by: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    use_start: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    use_end: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # [{"start": iso, "end": iso}] -- private, never published.
    pickup_windows: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    service_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    service_time_windows: Mapped[list | None] = mapped_column(JSON)
    area: Mapped[str | None] = mapped_column(String(80))  # coarse campus area, public

    visibility: Mapped[str] = mapped_column(String(10), nullable=False, default="private", index=True)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="draft", index=True)

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    requester = relationship("Profile", lazy="joined")

    def to_owner_dict(self) -> dict:
        result = {
            "id": self.id,
            "requester_id": self.requester_id,
            "original_text": self.original_text,
            "normalized": self.normalized or {},
            "modes": self.modes or [],
            "budget_cents": self.budget_cents,
            "max_deposit_cents": self.max_deposit_cents,
            "needed_by": iso_utc(self.needed_by),
            "use_start": iso_utc(self.use_start),
            "use_end": iso_utc(self.use_end),
            "pickup_windows": self.pickup_windows or [],
            "area": self.area,
            "visibility": self.visibility,
            "status": self.status,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }
        if "service" in (self.modes or []):
            for key in ("max_deposit_cents", "use_start", "use_end", "pickup_windows"):
                result.pop(key)
            result.update(service_duration_minutes=self.service_duration_minutes,
                          service_time_windows=self.service_time_windows or [])
        return result

    def to_public_dict(self) -> dict:
        """Sanitized shape for the public request feed."""
        normalized = self.normalized or {}
        needed_by = self.needed_by
        result = {
            "id": self.id,
            "requester": self.requester.to_public_dict() if self.requester else None,
            "category": normalized.get("category"),
            "modes": self.modes or [],
            "required_specifications": normalized.get("required_specifications") or {},
            "preferred_specifications": normalized.get("preferred_specifications") or {},
            "budget_cents": self.budget_cents,
            # Date only: precise schedules stay private.
            "needed_by_date": needed_by.date().isoformat() if needed_by else None,
            "area": self.area,
            "status": self.status,
            "created_at": iso_utc(self.created_at),
        }
        if "service" in (self.modes or []):
            result["service_duration_minutes"] = self.service_duration_minutes
        return result
