"""Supabase Auth adapter tests: provider responses are mocked, never live calls."""

import io
import json
import urllib.error

import pytest

from server.app import create_app


class ProviderResponse:
    def __init__(self, body):
        self.body = body

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return self.body


@pytest.fixture
def supabase_client(tmp_path):
    app = create_app({
        "TESTING": True,
        "APP_ENV": "development",
        "AUTH_MODE": "supabase",
        "SUPABASE_URL": "https://example.supabase.co",
        "SUPABASE_ANON_KEY": "public-test-key",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{tmp_path / 'supabase-test.sqlite3'}",
        "UPLOAD_DIR": str(tmp_path / "uploads"),
    })
    from server.db import db
    with app.app_context():
        db.create_all()
        yield app.test_client()
        db.session.remove()
        db.drop_all()


def test_confirmed_unc_email_creates_private_profile(supabase_client, monkeypatch):
    def fake_urlopen(request, timeout):
        assert request.full_url == "https://example.supabase.co/auth/v1/user"
        assert request.get_header("Authorization") == "Bearer test-access-token"
        assert request.get_header("Apikey") == "public-test-key"
        assert timeout > 0
        return ProviderResponse(json.dumps({
            "id": "provider-user-id", "email": "  Alice@UNC.EDU ",
            "email_confirmed_at": "2026-01-01T00:00:00Z",
        }).encode())

    monkeypatch.setattr("server.auth.identity.urllib.request.urlopen", fake_urlopen)
    response = supabase_client.get("/api/me", headers={"Authorization": "Bearer test-access-token"})
    assert response.status_code == 200
    profile = response.get_json()["profile"]
    assert profile["verification_source"] == "supabase"
    assert profile["confirmed_email_domain"] == "unc.edu"
    assert profile["is_demo"] is False
    assert "email" not in profile
    assert "alice@unc.edu" not in response.get_data(as_text=True).lower()


@pytest.mark.parametrize("payload,code", [
    ({"id": "u1", "email": "a@unc.edu", "email_confirmed_at": None}, "email_not_confirmed"),
    ({"id": "u1", "email": "a@unc.edu.evil.com", "email_confirmed_at": "2026-01-01"}, "domain_not_allowed"),
])
def test_unconfirmed_or_wrong_domain(supabase_client, monkeypatch, payload, code):
    monkeypatch.setattr("server.auth.identity.urllib.request.urlopen", lambda *_args, **_kwargs: ProviderResponse(json.dumps(payload).encode()))
    response = supabase_client.get("/api/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 403
    assert response.get_json()["error"]["code"] == code


def test_invalid_token(supabase_client, monkeypatch):
    def invalid(*_args, **_kwargs):
        raise urllib.error.HTTPError("https://example.supabase.co/auth/v1/user", 401, "Unauthorized", {}, io.BytesIO())

    monkeypatch.setattr("server.auth.identity.urllib.request.urlopen", invalid)
    response = supabase_client.get("/api/me", headers={"Authorization": "Bearer expired"})
    assert response.status_code == 401
    assert response.get_json()["error"]["code"] == "invalid_token"


def test_provider_failure_fails_closed(supabase_client, monkeypatch):
    def unavailable(*_args, **_kwargs):
        raise urllib.error.URLError("network down")

    monkeypatch.setattr("server.auth.identity.urllib.request.urlopen", unavailable)
    response = supabase_client.get("/api/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "auth_unavailable"
    assert "network down" not in response.get_data(as_text=True)


@pytest.mark.parametrize("body", [b"[]", b"not json", b'{"id": 9, "email": "a@unc.edu", "email_confirmed_at": true}', b'{"id": "u1", "email": 7, "email_confirmed_at": null}', b'{"id": "u1", "email": "a@unc.edu"}'])
def test_malformed_provider_response_fails_closed(supabase_client, monkeypatch, body):
    monkeypatch.setattr("server.auth.identity.urllib.request.urlopen", lambda *_args, **_kwargs: ProviderResponse(body))
    response = supabase_client.get("/api/me", headers={"Authorization": "Bearer token"})
    assert response.status_code == 503
    assert response.get_json()["error"]["code"] == "auth_unavailable"


def test_production_rejects_sandbox_and_development_secret(tmp_path):
    common = {"APP_ENV": "production", "UPLOAD_DIR": str(tmp_path / "uploads")}
    with pytest.raises(RuntimeError, match="AUTH_MODE=supabase"):
        create_app({**common, "AUTH_MODE": "sandbox", "SANDBOX_USERS": ["a@unc.edu"], "SECRET_KEY": "strong-secret"})
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({**common, "AUTH_MODE": "supabase", "SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "public-key", "SECRET_KEY": "dev-only-change-me"})
    create_app({**common, "AUTH_MODE": "supabase", "SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "public-key", "SECRET_KEY": "strong-secret"})
