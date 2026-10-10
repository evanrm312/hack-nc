"""Shared SQLAlchemy handle, migration handle, and small helpers.

Owned by Person 1. Import ``db`` from here in models and routes.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone

from flask_migrate import Migrate
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()
migrate = Migrate()


def new_id() -> str:
    """IDs are opaque strings (UUID4 hex) per docs/contracts.md."""
    return uuid.uuid4().hex


def utcnow() -> datetime:
    """Timezone-aware current UTC time. Persist timestamps in UTC."""
    return datetime.now(timezone.utc)


def iso_utc(value: datetime | None) -> str | None:
    """Serialize a datetime as ISO 8601 UTC with a trailing Z.

    SQLite drops tzinfo on the way back out, so a naive value is assumed to
    already be UTC and gets the zone re-attached.
    """
    if value is None:
        return None
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    value = value.astimezone(timezone.utc)
    return value.isoformat(timespec="seconds").replace("+00:00", "Z")
