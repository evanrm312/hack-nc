"""Private, transactional exchange notifications. No message content is copied."""
from sqlalchemy import DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from datetime import datetime
from ..db import db, iso_utc, new_id, utcnow

class Notification(db.Model):
    __tablename__ = 'notifications'
    __table_args__ = (UniqueConstraint('recipient_id', 'event_key', name='uq_notification_event'),)
    id: Mapped[str] = mapped_column(String(32), primary_key=True, default=new_id)
    recipient_id: Mapped[str] = mapped_column(ForeignKey('profiles.id'), nullable=False, index=True)
    exchange_id: Mapped[str] = mapped_column(ForeignKey('exchanges.id'), nullable=False, index=True)
    event_key: Mapped[str] = mapped_column(String(200), nullable=False)
    kind: Mapped[str] = mapped_column(String(40), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    read_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    exchange = relationship("Exchange")

    def to_dict(self):
        accessible = self.exchange is not None and self.recipient_id in self.exchange.participant_ids
        return {'id': self.id, 'kind': self.kind, 'exchange_id': self.exchange_id,
                'url': '/exchanges/' + self.exchange_id if accessible else None, 'accessible': accessible, 'created_at': iso_utc(self.created_at),
                'read_at': iso_utc(self.read_at)}
