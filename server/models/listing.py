"""Listing: an item an owner offers for sale, borrowing, or both.

Money columns are integer USD cents and null means unknown/not offered.
``active_exchange_id`` plus ``status`` back the atomic reservation helper in
server/reservation.py: one active reservation per physical item.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import UniqueConstraint, Boolean, JSON, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import db, iso_utc, new_id, utcnow

LISTING_MODES = ("sale", "borrow", "service")
SERVICE_CATEGORIES = (
    "tutoring", "proofreading", "moving help", "tech help",
    "repair and mending", "bike repair", "photography", "event help",
)
LISTING_STATUSES = ("available", "reserved", "sold", "withdrawn", "draft")


class Listing(db.Model):
    __tablename__ = "listings"

    __table_args__ = (UniqueConstraint("owner_id","creation_key",name="uq_listings_creation"),)
    creation_key: Mapped[str | None] = mapped_column(String(80))
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64))
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False, index=True)

    title: Mapped[str] = mapped_column(String(120), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    description: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    condition: Mapped[str | None] = mapped_column(String(40))
    accessories: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    known_defects: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    allowed_modes: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    sale_price_cents: Mapped[int | None] = mapped_column(Integer)
    rental_fee_cents: Mapped[int | None] = mapped_column(Integer)
    proposed_item_value_cents: Mapped[int | None] = mapped_column(Integer)
    collateral_percent: Mapped[int | None] = mapped_column(Integer)  # 0-100, default 100 for loans
    service_price_cents: Mapped[int | None] = mapped_column(Integer)
    service_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    service_available_windows: Mapped[list | None] = mapped_column(JSON)

    # {"available_from": iso|null, "available_until": iso|null, "notes": str|null}
    availability: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    meeting_spot_ids: Mapped[list] = mapped_column(JSON, nullable=False, default=list)

    status: Mapped[str] = mapped_column(String(20), nullable=False, default="available", index=True)
    active_exchange_id: Mapped[str | None] = mapped_column(String(32), index=True)
    publication_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default=db.false())
    public_photo_path: Mapped[str | None] = mapped_column(String(255))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    owner = relationship("Profile", lazy="joined")

    def to_dict(self) -> dict:
        """Public listing shape (docs/contracts.md -> Listing)."""
        result = {
            "id": self.id,
            "owner_id": self.owner_id,
            "owner": self.owner.to_public_dict() if self.owner else None,
            "title": self.title,
            "category": self.category,
            "description": self.description,
            "specifications": self.specifications or {},
            "condition": self.condition,
            "accessories": self.accessories or [],
            "known_defects": self.known_defects or [],
            "allowed_modes": self.allowed_modes or [],
            "sale_price_cents": self.sale_price_cents,
            "rental_fee_cents": self.rental_fee_cents,
            "proposed_item_value_cents": self.proposed_item_value_cents,
            "collateral_percent": self.collateral_percent,
            "availability": self.availability or {},
            "meeting_spot_ids": self.meeting_spot_ids or [],
            "status": self.status,
            "active_exchange_id": self.active_exchange_id,
            "public_photo_url": f"/media/public/{self.public_photo_path}" if self.public_photo_path else None,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }
        if "service" in (self.allowed_modes or []):
            for key in ("specifications", "condition", "accessories", "known_defects",
                        "sale_price_cents", "rental_fee_cents", "proposed_item_value_cents",
                        "collateral_percent", "availability", "meeting_spot_ids"):
                result.pop(key)
            result.update(
                service_price_cents=self.service_price_cents,
                service_duration_minutes=self.service_duration_minutes,
                service_available_windows=self.service_available_windows or [],
            )
        return result
