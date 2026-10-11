"""Exchange, OfferRevision, Message, Evidence.

Person 4 builds the workflow on top of these. Status transitions are listed
in docs/contracts.md -> "Exchange status rules" and must be enforced in
Python (server/exchanges/), never trusted from the client.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import CheckConstraint, JSON, Boolean, DateTime, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from ..db import db, iso_utc, new_id, utcnow

EXCHANGE_MODES = ("sale", "borrow", "service")
EXCHANGE_STATUSES = (
    "negotiating",
    "reserved",
    "scheduled",
    "on_loan",
    "return_pending",
    "completed",
    "disputed",
    "cancelled",
)
EVIDENCE_STAGES = ("pre_handoff", "handoff", "pre_return", "post_return")


class Exchange(db.Model):
    __tablename__ = "exchanges"
    __table_args__ = (UniqueConstraint("requester_id","creation_key",name="uq_exchanges_creation"),
        CheckConstraint("club_review_state IN ('not_required','awaiting_participants','pending','approved','changes_requested')", name="ck_exchange_club_review"),
        CheckConstraint("(club_id IS NULL AND club_review_state = 'not_required') OR (club_id IS NOT NULL AND club_review_state != 'not_required')", name="ck_exchange_club_consistency"),)
    club_id: Mapped[str | None] = mapped_column(ForeignKey("clubs.id"), index=True)
    club_review_state: Mapped[str] = mapped_column(String(24), nullable=False, default="not_required", server_default="not_required")
    club_review_note: Mapped[str | None] = mapped_column(String(300))
    club_reviewed_by: Mapped[str | None] = mapped_column(ForeignKey("profiles.id"))
    club_reviewed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    club_review_version: Mapped[int | None] = mapped_column(Integer)
    club = relationship("Club", lazy="joined")
    creation_key: Mapped[str | None] = mapped_column(String(80))
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64))

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    listing_id: Mapped[str] = mapped_column(String(32), ForeignKey("listings.id"), nullable=False, index=True)
    owner_id: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False, index=True)
    requester_id: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False, index=True)
    source_request_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("need_requests.id"))

    mode: Mapped[str] = mapped_column(String(10), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False, default="negotiating", index=True)
    current_offer_revision: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    dispute_reason: Mapped[str | None] = mapped_column(Text)
    owner_service_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requester_service_confirmed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow
    )

    offers = relationship("OfferRevision", back_populates="exchange", order_by="OfferRevision.version")

    @property
    def participant_ids(self) -> set[str]:
        return {self.owner_id, self.requester_id}

    def to_dict(self) -> dict:
        result = {
            "club": self.club.to_dict() if self.club else None,
            "club_review_state": self.club_review_state,
            "club_review_note": self.club_review_note,
            "id": self.id,
            "listing_id": self.listing_id,
            "owner_id": self.owner_id,
            "requester_id": self.requester_id,
            "source_request_id": self.source_request_id,
            "mode": self.mode,
            "status": self.status,
            "current_offer_revision": self.current_offer_revision,
            "cancellation_reason": self.cancellation_reason,
            "dispute_reason": self.dispute_reason,
            "created_at": iso_utc(self.created_at),
            "updated_at": iso_utc(self.updated_at),
        }
        if self.mode == "service":
            result["owner_service_confirmed_at"] = iso_utc(self.owner_service_confirmed_at)
            result["requester_service_confirmed_at"] = iso_utc(self.requester_service_confirmed_at)
            result["payment_notice"] = "Simulated: no real funds are reserved or charged."
        return result


class OfferRevision(db.Model):
    __tablename__ = "offer_revisions"
    __table_args__ = (UniqueConstraint("exchange_id", "version", name="uq_offer_exchange_version"),)

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    exchange_id: Mapped[str] = mapped_column(String(32), ForeignKey("exchanges.id"), nullable=False, index=True)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    created_by: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False)

    # Monetary terms, integer cents. Sale uses sale_price_cents; borrowing uses
    # rental_fee_cents + agreed_item_value_cents + deposit_cents.
    sale_price_cents: Mapped[int | None] = mapped_column(Integer)
    rental_fee_cents: Mapped[int | None] = mapped_column(Integer)
    agreed_item_value_cents: Mapped[int | None] = mapped_column(Integer)
    deposit_cents: Mapped[int | None] = mapped_column(Integer)
    service_price_cents: Mapped[int | None] = mapped_column(Integer)
    service_duration_minutes: Mapped[int | None] = mapped_column(Integer)
    service_scheduled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    service_delivery: Mapped[str | None] = mapped_column(String(16))
    service_meeting_spot_id: Mapped[str | None] = mapped_column(ForeignKey("meeting_spots.id"))
    # Required true when deposit_cents < agreed_item_value_cents.
    lower_deposit_acknowledged: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # {"condition": str, "accessories": [..], "known_defects": [..]}
    condition_snapshot: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    pickup_meeting_spot_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("meeting_spots.id"))
    pickup_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    return_meeting_spot_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("meeting_spots.id"))
    return_deadline: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    pricing_range_version: Mapped[int | None] = mapped_column(Integer)
    price_reference_id: Mapped[str | None] = mapped_column(String(32), ForeignKey("price_references.id"))

    owner_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    requester_accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    exchange = relationship("Exchange", back_populates="offers")

    @property
    def uncovered_value_cents(self) -> int | None:
        if self.agreed_item_value_cents is None or self.deposit_cents is None:
            return None
        return max(self.agreed_item_value_cents - self.deposit_cents, 0)

    def to_dict(self) -> dict:
        result = {
            "id": self.id,
            "exchange_id": self.exchange_id,
            "version": self.version,
            "created_by": self.created_by,
            "sale_price_cents": self.sale_price_cents,
            "rental_fee_cents": self.rental_fee_cents,
            "agreed_item_value_cents": self.agreed_item_value_cents,
            "deposit_cents": self.deposit_cents,
            "uncovered_value_cents": self.uncovered_value_cents,
            "lower_deposit_acknowledged": self.lower_deposit_acknowledged,
            "condition_snapshot": self.condition_snapshot or {},
            "pickup_meeting_spot_id": self.pickup_meeting_spot_id,
            "pickup_at": iso_utc(self.pickup_at),
            "return_meeting_spot_id": self.return_meeting_spot_id,
            "return_deadline": iso_utc(self.return_deadline),
            "pricing_range_version": self.pricing_range_version,
            "price_reference_id": self.price_reference_id,
            "owner_accepted_at": iso_utc(self.owner_accepted_at),
            "requester_accepted_at": iso_utc(self.requester_accepted_at),
            "created_at": iso_utc(self.created_at),
        }
        if self.exchange and self.exchange.mode == "service":
            for key in ("sale_price_cents", "rental_fee_cents", "agreed_item_value_cents",
                        "deposit_cents", "uncovered_value_cents", "lower_deposit_acknowledged",
                        "condition_snapshot", "pickup_meeting_spot_id", "pickup_at",
                        "return_meeting_spot_id", "return_deadline", "pricing_range_version",
                        "price_reference_id"):
                result.pop(key)
            result.update(service_delivery=self.service_delivery or "remote",
                          service_meeting_spot_id=self.service_meeting_spot_id,
                          service_price_cents=self.service_price_cents,
                          service_duration_minutes=self.service_duration_minutes,
                          service_scheduled_at=iso_utc(self.service_scheduled_at))
        return result


class Message(db.Model):
    __tablename__ = "messages"
    __table_args__ = (UniqueConstraint("sender_id","creation_key",name="uq_messages_creation"),)
    creation_key: Mapped[str | None] = mapped_column(String(80))
    creation_fingerprint: Mapped[str | None] = mapped_column(String(64))

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    exchange_id: Mapped[str] = mapped_column(String(32), ForeignKey("exchanges.id"), nullable=False, index=True)
    sender_id: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exchange_id": self.exchange_id,
            "sender_id": self.sender_id,
            "body": self.body,
            "created_at": iso_utc(self.created_at),
        }


class Evidence(db.Model):
    """Private condition photos. Never served from a public URL."""

    __tablename__ = "evidence"

    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    exchange_id: Mapped[str] = mapped_column(String(32), ForeignKey("exchanges.id"), nullable=False, index=True)
    uploader_id: Mapped[str] = mapped_column(String(32), ForeignKey("profiles.id"), nullable=False)
    stage: Mapped[str] = mapped_column(String(20), nullable=False)
    private_storage_path: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(40), nullable=False)
    # {"<profile_id>": iso_timestamp} of participants who acknowledged it.
    acknowledged_by: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "exchange_id": self.exchange_id,
            "uploader_id": self.uploader_id,
            "stage": self.stage,
            "content_type": self.content_type,
            "acknowledged_by": self.acknowledged_by or {},
            # Participants fetch bytes through the authorized evidence endpoint.
            "url": f"/api/exchanges/{self.exchange_id}/evidence/{self.id}",
            "created_at": iso_utc(self.created_at),
        }
