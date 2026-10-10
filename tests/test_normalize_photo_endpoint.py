"""Reference-photo request proposals never persist the uploaded image."""

import io
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import Mock

import pytest

from server.db import db
from server.intelligence.normalize import manual
from server.models import Listing, NeedRequest


URL = "/api/requests/normalize-photo"
PNG = b"\x89PNG\r\n\x1a\nmock-photo"


def upload(client, headers, photo=PNG, mime="image/png", **fields):
    data = {"photo": (io.BytesIO(photo), "reference.png", mime), **fields}
    return client.post(URL, data=data, headers=headers)


def assert_error(response, status, code, field=None):
    assert response.status_code == status
    error = response.get_json()["error"]
    assert error["code"] == code
    assert isinstance(error["message"], str)
    assert isinstance(error["fields"], dict)
    if field:
        assert field in error["fields"]


def test_normalize_photo_requires_verified_user(client, alice, mallory, monkeypatch):
    helper = Mock()
    monkeypatch.setattr("server.routes.requests.normalize_reference_image", helper)
    assert_error(upload(client, {}, photo=PNG), 401, "auth_required")
    assert_error(upload(client, mallory, photo=PNG), 403, "domain_not_allowed")
    helper.assert_not_called()


def test_normalize_photo_requires_photo_and_valid_text(client, alice, monkeypatch):
    helper = Mock()
    monkeypatch.setattr("server.routes.requests.normalize_reference_image", helper)
    assert_error(client.post(URL, data={}, headers=alice), 400, "validation_error", "photo")
    assert_error(client.post(URL, data={"text": "hello"}, headers=alice), 400, "validation_error", "photo")
    assert_error(upload(client, alice, text="x" * 4001), 400, "validation_error", "text")
    helper.assert_not_called()


@pytest.mark.parametrize("photo,mime,code", [
    (b"", "image/png", "invalid_image"),
    (PNG, "image/gif", "unsupported_image"),
    (b"not-an-image", "image/png", "unsupported_image"),
    (PNG, "image/jpeg", "unsupported_image"),
])
def test_rejected_photo_never_invokes_gemini(client, alice, monkeypatch, photo, mime, code):
    monkeypatch.setenv("GEMINI_API_KEY", "mock-only-key")
    gemini = Mock()
    monkeypatch.setattr("server.intelligence.vision.normalization.genai.Client", gemini)
    assert_error(upload(client, alice, photo=photo, mime=mime), 400, code)
    gemini.assert_not_called()


@pytest.mark.parametrize("configured_limit,size", [
    (64 * 1024, 64 * 1024 + 1),
    (6 * 1024 * 1024, 5 * 1024 * 1024 + 1),
])
def test_oversized_photo_rejected_before_helper(client, app, alice, monkeypatch, configured_limit, size):
    app.config["MAX_UPLOAD_BYTES"] = configured_limit
    app.config["MAX_CONTENT_LENGTH"] = size + 1024
    helper = Mock()
    monkeypatch.setattr("server.routes.requests.normalize_reference_image", helper)
    assert_error(upload(client, alice, photo=PNG + b"x" * (size - len(PNG))), 413, "payload_too_large")
    helper.assert_not_called()


def test_valid_photo_passes_bounded_bytes_mime_server_time_and_text(client, app, alice, monkeypatch):
    now = datetime(2026, 10, 10, 16, tzinfo=timezone.utc)
    proposal = manual("Borrow a suit like this")
    proposal["source"] = "gemini"
    proposal["preferred_specifications"] = {"color": "navy"}
    helper = Mock(return_value=proposal)
    monkeypatch.setattr("server.routes.requests.normalize_reference_image", helper)
    monkeypatch.setattr("server.routes.requests.utcnow", lambda: now)

    response = upload(client, alice, text="  Borrow a suit like this  ")
    assert response.status_code == 200
    assert response.get_json() == {"normalized": proposal, "fixture": False}
    helper.assert_called_once_with(PNG, "image/png", now, app.config["DISPLAY_TIMEZONE"], "Borrow a suit like this")
    with app.app_context():
        assert db.session.query(NeedRequest).count() == 0
        assert db.session.query(Listing).count() == 0
    assert not any(path.is_file() for path in Path(app.config["UPLOAD_DIR"]).rglob("*"))


def test_image_only_manual_fallback_is_returned_without_request_creation(client, app, alice, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    response = upload(client, alice)
    assert response.status_code == 200
    assert response.get_json() == {"normalized": manual(""), "fixture": False}
    assert response.get_json()["normalized"]["modes"] is None
    assert response.get_json()["normalized"]["original_text"] == ""
    with app.app_context():
        assert db.session.query(NeedRequest).count() == 0


def test_optional_text_accepts_4000_characters(client, alice, monkeypatch):
    helper = Mock(return_value=manual("x" * 4000))
    monkeypatch.setattr("server.routes.requests.normalize_reference_image", helper)
    response = upload(client, alice, text="x" * 4000)
    assert response.status_code == 200
    assert helper.call_args.args[-1] == "x" * 4000
