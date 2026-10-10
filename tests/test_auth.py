"""Verified identity: /api/me, domain rules, sandbox labeling, no email leaks."""

from server.auth.identity import domain_allowed, email_domain
from tests.conftest import ALICE, LOOKALIKE, auth


def test_me_requires_token(client):
    resp = client.get("/api/me")
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "auth_required"


def test_me_rejects_garbage_token(client):
    resp = client.get("/api/me", headers={"Authorization": "Bearer nonsense"})
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "invalid_token"


def test_me_rejects_unlisted_sandbox_user(client):
    resp = client.get("/api/me", headers=auth("stranger@unc.edu"))
    assert resp.status_code == 401
    assert resp.get_json()["error"]["code"] == "invalid_token"


def test_me_returns_labeled_sandbox_profile_without_email(client, alice):
    resp = client.get("/api/me", headers=alice)
    assert resp.status_code == 200
    profile = resp.get_json()["profile"]
    assert profile["confirmed_email_domain"] == "unc.edu"
    assert profile["verification_source"] == "sandbox"
    assert profile["is_demo"] is True
    assert "not verified" in profile["badge"].lower()
    assert "email" not in profile
    assert ALICE not in resp.get_data(as_text=True)
    assert "alice" not in profile["display_name"].lower()


def test_me_is_stable_across_requests(client, alice):
    first = client.get("/api/me", headers=alice).get_json()["profile"]["id"]
    second = client.get("/api/me", headers=alice).get_json()["profile"]["id"]
    assert first == second


def test_wrong_domain_is_forbidden(client, mallory):
    resp = client.get("/api/me", headers=mallory)
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "domain_not_allowed"


def test_lookalike_domain_is_forbidden(client):
    resp = client.get("/api/me", headers=auth(LOOKALIKE))
    assert resp.status_code == 403
    assert resp.get_json()["error"]["code"] == "domain_not_allowed"


def test_uppercase_email_normalizes(client):
    resp = client.get("/api/me", headers=auth("ALICE@UNC.EDU"))
    assert resp.status_code == 200


def test_update_display_name(client, alice):
    resp = client.patch("/api/me", json={"display_name": "  Tar Heel  "}, headers=alice)
    assert resp.status_code == 200
    assert resp.get_json()["profile"]["display_name"] == "Tar Heel"
    bad = client.patch("/api/me", json={"display_name": ""}, headers=alice)
    assert bad.status_code == 400
    assert "display_name" in bad.get_json()["error"]["fields"]


def test_domain_helpers_are_exact():
    assert email_domain("X@UNC.EDU") == "unc.edu"
    assert domain_allowed("x@unc.edu", "unc.edu")
    assert not domain_allowed("x@unc.edu.evil.com", "unc.edu")
    assert not domain_allowed("x@notunc.edu", "unc.edu")
    assert not domain_allowed("x@sub.unc.edu", "unc.edu")
    assert not domain_allowed("no-at-sign", "unc.edu")
