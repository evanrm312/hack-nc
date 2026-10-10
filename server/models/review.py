"""Review: one per participant per completed exchange."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from ..db import db, iso_utc, new_id, utcnow

# Structured answers: each key maps to "yes" | "no" | "not_applicable".
REVIEW_FIELDS = (
    "description_accurate",
    "condition_as_agreed",
    "punctual",
    "communicative",
    "returned_on_time",  # loans only; "not_applicable" for sales
)


class Review(db.Model):
    __tablename__ = "reviews"
    __table_args__ = (UniqueConstraint("exchange_id", "reviewer_id", name="uq_review_exchange_reviewer"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    exchange_id: Mapped[str] = mapped_column(String(32), ForeignKey("exchanges.id"), nullable=False, index=True)
    reviewer_id: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False)
    reviewee_id: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False, index=True)
    stars: Mapped[int] = mapped_column(Integer, nullable=False)  # 1-5
    structured_answers: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    comment: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exchange_id": self.exchange_id,
            "reviewer_id": self.reviewer_id,
            "reviewee_id": self.reviewee_id,
            "stars": self.stars,
            "structured_answers": self.structured_answers or {},
            "comment": self.comment,
            "created_at": iso_utc(self.created_at),
        }
