"""Supabase Auth adapter tests: provider responses are mocked, never live calls."""
from tests.conftest import publish_listing

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


def test_supabase_identity_owns_normalized_request_and_matches_real_catalog(supabase_client, monkeypatch):
    users = {
        "owner-token": {"id": "provider-owner", "email": "owner@unc.edu", "email_confirmed_at": "2026-01-01T00:00:00Z"},
        "requester-token": {"id": "provider-requester", "email": "requester@unc.edu", "email_confirmed_at": "2026-01-01T00:00:00Z"},
    }

    def fake_urlopen(request, timeout):
        token = request.get_header("Authorization").removeprefix("Bearer ")
        return ProviderResponse(json.dumps(users[token]).encode())

    monkeypatch.setattr("server.auth.identity.urllib.request.urlopen", fake_urlopen)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    owner = {"Authorization": "Bearer owner-token"}
    requester = {"Authorization": "Bearer requester-token"}

    listing_response = supabase_client.post("/api/listings", json={
        "title": "Navy suit 40R", "category": "formalwear", "allowed_modes": ["borrow"],
        "description": "Synthetic suit for authentication integration.",
        "specifications": {"jacket_size": "40R"}, "rental_fee_cents": 0,
        "proposed_item_value_cents": 20000, "collateral_percent": 30,
    }, headers=owner)
    assert listing_response.status_code == 201
    listing = publish_listing(supabase_client, owner, listing_response.get_json()["listing"])

    normalized_response = supabase_client.post("/api/requests/normalize", json={"text": "I need a 40R suit"}, headers=requester)
    assert normalized_response.status_code == 200
    normalized = normalized_response.get_json()["normalized"]
    assert normalized_response.get_json()["fixture"] is False
    assert normalized["source"] == "manual"
    normalized["category"] = "formalwear"  # user confirms editable fallback fields
    normalized["required_specifications"] = {"jacket_size": "40R"}

    created = supabase_client.post("/api/requests", json={
        "original_text": "I need a 40R suit", "normalized": normalized,
        "modes": ["borrow"], "budget_cents": 1000, "max_deposit_cents": 6000,
        "requester_id": listing["owner_id"],  # must never claim the listing owner's identity
    }, headers=requester)
    assert created.status_code == 201
    need = created.get_json()["request"]
    assert need["requester_id"] != listing["owner_id"]
    url = f"/api/requests/{need['id']}"
    assert supabase_client.get(url, headers=owner).status_code == 404
    assert supabase_client.get(url + "/matches", headers=owner).status_code == 403
    assert supabase_client.post(url + "/publish", headers=owner).status_code == 403

    matches = supabase_client.get(url + "/matches", headers=requester)
    assert matches.status_code == 200
    result = matches.get_json()
    assert result["source"] == "deterministic" and result["fixture"] is False
    assert [entry["listing_id"] for entry in result["confirmed"]] == [listing["id"]]
    assert result["confirmed"][0]["listing"]["title"] == listing["title"]

    published = supabase_client.post(url + "/publish", headers=requester)
    assert published.status_code == 200
    public_view = supabase_client.get(url, headers=owner).get_json()["request"]
    assert "original_text" not in public_view and "pickup_windows" not in public_view
    assert "requester@unc.edu" not in str(public_view)


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
    common = {"APP_ENV": "production", "UPLOAD_DIR": str(tmp_path / "uploads"), "SQLALCHEMY_DATABASE_URI": "postgresql+psycopg://unused@127.0.0.1/unused"}
    with pytest.raises(RuntimeError, match="AUTH_MODE=supabase"):
        create_app({**common, "AUTH_MODE": "sandbox", "SANDBOX_USERS": ["a@unc.edu"], "SECRET_KEY": "test-only-production-secret-32-characters"})
    with pytest.raises(RuntimeError, match="SECRET_KEY"):
        create_app({**common, "AUTH_MODE": "supabase", "SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "public-key", "SECRET_KEY": "dev-only-change-me"})
    create_app({**common, "AUTH_MODE": "supabase", "SUPABASE_URL": "https://example.supabase.co", "SUPABASE_ANON_KEY": "public-key", "SECRET_KEY": "test-only-production-secret-32-characters"})
