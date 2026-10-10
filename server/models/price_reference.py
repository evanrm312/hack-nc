"""PriceReference: documented comparable price range used by evaluate_price.

``is_fixture`` rows are hand-labeled demo data and must be shown as such.
Sale ranges and rental ranges are separate rows (``price_type``), and a rental
range carries its ``duration_basis``. Never derive deposits or item value from
a rental range.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Boolean, Date, DateTime, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from ..db import db, iso_utc, new_id, utcnow

PRICE_TYPES = ("sale", "rental")


class PriceReference(db.Model):
    __tablename__ = "price_references"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    category: Mapped[str] = mapped_column(String(60), nullable=False, index=True)
    specifications: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    condition: Mapped[str | None] = mapped_column(String(40))
    price_type: Mapped[str] = mapped_column(String(10), nullable=False)  # sale | rental
    duration_basis: Mapped[str | None] = mapped_column(String(20))  # e.g. "per_day", null for sale
    lower_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    upper_cents: Mapped[int] = mapped_column(Integer, nullable=False)
    sample_count: Mapped[int] = mapped_column(Integer, nullable=False)
    source: Mapped[str] = mapped_column(String(255), nullable=False)
    observed_from: Mapped[date | None] = mapped_column(Date)
    observed_to: Mapped[date | None] = mapped_column(Date)
    is_fixture: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "category": self.category,
            "specifications": self.specifications or {},
            "condition": self.condition,
            "price_type": self.price_type,
            "duration_basis": self.duration_basis,
            "lower_cents": self.lower_cents,
            "upper_cents": self.upper_cents,
            "sample_count": self.sample_count,
            "source": self.source,
            "observed_from": self.observed_from.isoformat() if self.observed_from else None,
            "observed_to": self.observed_to.isoformat() if self.observed_to else None,
            "is_fixture": self.is_fixture,
            "version": self.version,
            "created_at": iso_utc(self.created_at),
        }
