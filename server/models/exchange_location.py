from datetime import datetime
from sqlalchemy import DateTime, ForeignKey, Float, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from ..db import db, new_id, iso_utc

class ExchangeLocation(db.Model):
    __tablename__ = 'exchange_locations'
    __table_args__ = (UniqueConstraint('exchange_id','participant_id',name='uq_exchange_location_participant'),)
    id: Mapped[str] = mapped_column(String(32),primary_key=True,default=new_id)
    exchange_id: Mapped[str] = mapped_column(ForeignKey('exchanges.id'),nullable=False,index=True)
    participant_id: Mapped[str] = mapped_column(ForeignKey('profiles.id'),nullable=False)
    landmark: Mapped[str | None] = mapped_column(String(120))
    latitude: Mapped[float | None] = mapped_column(Float)
    longitude: Mapped[float | None] = mapped_column(Float)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True),nullable=False)
    def to_dict(self):
        return dict(participant_id=self.participant_id,landmark=self.landmark,latitude=self.latitude,
                    longitude=self.longitude,expires_at=iso_utc(self.expires_at))
