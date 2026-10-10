"""Profiles and marketplace listings."""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from server.db import db


class Profile(db.Model):
    __tablename__ = "profile"

    # A verified provider user ID will be the key once authentication is added.
    id: Mapped[str] = mapped_column(String(255), primary_key=True)
    display_name: Mapped[str | None] = mapped_column(String(120))
    confirmed_email_domain: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    listings: Mapped[list["Listing"]] = relationship(back_populates="owner")


class Listing(db.Model):
    __tablename__ = "listing"
    __table_args__ = (
        CheckConstraint("mode IN ('sale', 'borrow', 'both')", name="valid_mode"),
        CheckConstraint(
            "status IN ('draft', 'active', 'reserved', 'sold', 'archived')",
            name="valid_status",
        ),
        CheckConstraint("sale_price_cents >= 0", name="sale_price_nonnegative"),
        CheckConstraint("rental_fee_cents >= 0", name="rental_fee_nonnegative"),
        CheckConstraint("proposed_item_value_cents >= 0", name="item_value_nonnegative"),
        CheckConstraint(
            "collateral_percent BETWEEN 0 AND 100", name="collateral_percent_range"
        ),
    )

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    owner_id: Mapped[str] = mapped_column(
        String(255), ForeignKey("profile.id"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    specifications: Mapped[dict | None] = mapped_column(JSON)
    condition: Mapped[str | None] = mapped_column(Text)
    accessories: Mapped[list | None] = mapped_column(JSON)
    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    sale_price_cents: Mapped[int | None] = mapped_column(nullable=True)
    rental_fee_cents: Mapped[int | None] = mapped_column(nullable=True)
    proposed_item_value_cents: Mapped[int | None] = mapped_column(nullable=True)
    collateral_percent: Mapped[int | None] = mapped_column(nullable=True)
    status: Mapped[str] = mapped_column(String(12), nullable=False, default="draft")
    public_photo_path: Mapped[str | None] = mapped_column(String(500))
    is_demo: Mapped[bool] = mapped_column(nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )

    owner: Mapped[Profile] = relationship(back_populates="listings")
