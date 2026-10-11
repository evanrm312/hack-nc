"""Shared pytest fixtures. Owned by Person 1; everyone may use these.

- ``app`` / ``client``: fresh SQLite file DB per test, sandbox auth, temp uploads.
- ``auth(email)``: Authorization header dict for a sandbox identity.
- ``alice`` / ``bob``: two verified @unc.edu users; ``mallory`` is @gmail.com.
"""

from __future__ import annotations

import pytest

from server.app import create_app
from server.db import db

ALICE = "alice@unc.edu"
BOB = "bob@unc.edu"
MALLORY = "mallory@gmail.com"  # wrong domain: resolves as an identity, fails the domain check
LOOKALIKE = "eve@unc.edu.evil.com"  # suffix attack: must be rejected


@pytest.fixture
def app(tmp_path):
    app = create_app(
        {
            "TESTING": True,
            "APP_ENV": "development",
            "SQLALCHEMY_DATABASE_URI": f"sqlite:///{(tmp_path / 'test.sqlite3').as_posix()}",
            "AUTH_MODE": "sandbox",
            "SANDBOX_USERS": [ALICE, BOB, MALLORY, LOOKALIKE],
            "ALLOWED_EMAIL_DOMAIN": "unc.edu",
            "STORAGE_BACKEND": "local",
            "UPLOAD_DIR": str(tmp_path / "uploads"),
            "MAX_UPLOAD_BYTES": 64 * 1024,
            "MAX_CONTENT_LENGTH": 128 * 1024,
        }
    )
    with app.app_context():
        db.create_all()
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()


def auth(email: str) -> dict:
    return {"Authorization": f"Bearer sandbox:{email}"}


@pytest.fixture
def alice():
    return auth(ALICE)


@pytest.fixture
def bob():
    return auth(BOB)


@pytest.fixture
def mallory():
    return auth(MALLORY)


LISTING_BODY = {
    "title": "Navy suit 40R",
    "category": "formalwear",
    "description": "Two-piece, worn twice.",
    "specifications": {"jacket_size": "40R", "color": "navy"},
    "condition": "good",
    "accessories": ["garment bag"],
    "known_defects": [],
    "allowed_modes": ["borrow", "sale"],
    "sale_price_cents": 9000,
    "rental_fee_cents": 1500,
    "proposed_item_value_cents": 20000,
    "collateral_percent": 100,
    "availability": {"notes": "weekday afternoons"},
}


def create_listing(client, headers, **overrides):
    body = {**LISTING_BODY, **overrides}
    resp = client.post("/api/listings", json=body, headers=headers)
    assert resp.status_code == 201, resp.get_json()
    return publish_listing(client, headers, resp.get_json()["listing"])


def publish_listing(client, headers, listing):
    from io import BytesIO
    from PIL import Image
    photo = BytesIO()
    Image.new("RGB", (3, 3), "blue").save(photo, format="PNG")
    photo.seek(0)
    response = client.post(f"/api/listings/{listing['id']}/publish", headers=headers,
                           data={"photo": (photo, "photo.png")})
    assert response.status_code == 200, response.get_json()
    return response.get_json()["listing"]
