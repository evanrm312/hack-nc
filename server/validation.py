"""Request-body validation helpers shared by Person 1 routes (and reusable by
Person 4). Gemini may propose values; this module is where Python enforces them.
"""

from __future__ import annotations

from datetime import datetime, timezone

from flask import request

from .errors import ApiError, validation_error

MAX_MONEY_CENTS = 100_000_000  # $1,000,000.00 sanity cap


def json_body() -> dict:
    """Return the JSON object body or raise a 400 in the standard shape."""
    data = request.get_json(silent=True)
    if data is None:
        raise ApiError(400, "invalid_json", "Request body must be a JSON object")
    if not isinstance(data, dict):
        raise ApiError(400, "invalid_json", "Request body must be a JSON object")
    return data


class FieldErrors:
    """Collects per-field problems and raises once."""

    def __init__(self) -> None:
        self.fields: dict[str, str] = {}

    def add(self, field: str, message: str) -> None:
        self.fields[field] = message

    def raise_if_any(self) -> None:
        if self.fields:
            raise validation_error(self.fields)


def money_cents(value, field: str, errors: FieldErrors, *, required: bool = False) -> int | None:
    """Validate integer USD cents. None/absent means unknown (allowed unless required)."""
    if value is None:
        if required:
            errors.add(field, "required")
        return None
    if isinstance(value, bool) or not isinstance(value, int):
        errors.add(field, "must be an integer number of cents")
        return None
    if value < 0:
        errors.add(field, "must not be negative")
        return None
    if value > MAX_MONEY_CENTS:
        errors.add(field, "exceeds maximum")
        return None
    return value


def percent(value, field: str, errors: FieldErrors) -> int | None:
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= 100:
        errors.add(field, "must be an integer from 0 to 100")
        return None
    return value


def string(value, field: str, errors: FieldErrors, *, required: bool = False, max_len: int = 2000) -> str | None:
    if value is None:
        if required:
            errors.add(field, "required")
        return None
    if not isinstance(value, str):
        errors.add(field, "must be a string")
        return None
    value = value.strip()
    if required and not value:
        errors.add(field, "required")
        return None
    if len(value) > max_len:
        errors.add(field, f"must be at most {max_len} characters")
        return None
    return value or None


def choice_list(value, field: str, errors: FieldErrors, allowed, *, required: bool = False) -> list | None:
    if value is None:
        if required:
            errors.add(field, "required")
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.add(field, "must be a list of strings")
        return None
    bad = [v for v in value if v not in allowed]
    if bad:
        errors.add(field, f"unknown values: {', '.join(bad)}; allowed: {', '.join(allowed)}")
        return None
    deduped = list(dict.fromkeys(value))
    if required and not deduped:
        errors.add(field, "must not be empty")
        return None
    return deduped


def string_list(value, field: str, errors: FieldErrors) -> list | None:
    if value is None:
        return None
    if not isinstance(value, list) or not all(isinstance(v, str) for v in value):
        errors.add(field, "must be a list of strings")
        return None
    return [v.strip() for v in value if v.strip()]


def time_windows(value, field: str, errors: FieldErrors, *, required: bool = False) -> list | None:
    """Validate explicit UTC windows for service availability or requested times."""
    if value is None:
        if required:
            errors.add(field, "required")
        return None
    if not isinstance(value, list):
        errors.add(field, "must be a list of {start, end}")
        return None
    if required and not value:
        errors.add(field, "must not be empty")
    cleaned = []
    for index, window in enumerate(value):
        if not isinstance(window, dict):
            errors.add(f"{field}[{index}]", "must be an object with start and end")
            continue
        start = datetime_utc(window.get("start"), f"{field}[{index}].start", errors)
        end = datetime_utc(window.get("end"), f"{field}[{index}].end", errors)
        if start is None or end is None:
            if window.get("start") is None:
                errors.add(f"{field}[{index}].start", "required")
            if window.get("end") is None:
                errors.add(f"{field}[{index}].end", "required")
        elif end <= start:
            errors.add(f"{field}[{index}]", "end must be after start")
        else:
            cleaned.append({"start": start.isoformat().replace("+00:00", "Z"),
                            "end": end.isoformat().replace("+00:00", "Z")})
    return cleaned


def json_object(value, field: str, errors: FieldErrors) -> dict | None:
    if value is None:
        return None
    if not isinstance(value, dict):
        errors.add(field, "must be an object")
        return None
    return value


def datetime_utc(value, field: str, errors: FieldErrors) -> datetime | None:
    """Parse an ISO 8601 timestamp that carries a timezone; store as UTC."""
    if value is None:
        return None
    if not isinstance(value, str):
        errors.add(field, "must be an ISO 8601 timestamp string")
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        errors.add(field, "must be an ISO 8601 timestamp, e.g. 2026-10-12T18:00:00Z")
        return None
    if parsed.tzinfo is None:
        errors.add(field, "must include a timezone offset (use Z for UTC)")
        return None
    return parsed.astimezone(timezone.utc)
