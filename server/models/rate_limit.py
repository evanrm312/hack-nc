"""Shared fixed-window counters. Subject identifiers are irreversible hashes."""
from sqlalchemy import Integer, String
from sqlalchemy.orm import Mapped, mapped_column
from ..db import db

class RateLimit(db.Model):
    __tablename__ = 'rate_limits'
    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    window: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
