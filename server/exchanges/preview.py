"""Run the existing Flask app with isolated, labeled exchange preview data.

    python -m server.exchanges.preview

This is local sandbox tooling. It does not change .env, production data,
shared seed code, authentication helpers, or the application entrypoint.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from flask_migrate import upgrade

from ..app import PROJECT_ROOT, create_app
from ..seed import seed_demo_data


def create_preview_app(data_dir: Path):
    data_dir = data_dir.resolve()
    app = create_app({
        "APP_ENV": "development",
        "AUTH_MODE": "sandbox",
        "SANDBOX_USERS": ["alice@unc.edu", "bob@unc.edu", "charlie@unc.edu"],
        "ALLOWED_EMAIL_DOMAIN": "unc.edu",
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{data_dir / 'preview.sqlite3'}",
        "STORAGE_BACKEND": "local",
        "UPLOAD_DIR": str(data_dir / "uploads"),
        "EXCHANGE_PREVIEW": True,
    })
    with app.app_context():
        upgrade()
        seed_demo_data()

    client = app.test_client()
    alice = {"Authorization": "Bearer sandbox:alice@unc.edu"}

    def checked(response):
        if response.status_code >= 400:
            raise RuntimeError(f"Preview setup failed: {response.get_json()}")
        return response.get_json()

    for name, label in (("alice", "Demo owner (Alice)"), ("bob", "Demo requester (Bob)"), ("charlie", "Demo third party (Charlie)")):
        checked(client.patch("/api/me", headers={"Authorization": f"Bearer sandbox:{name}@unc.edu"}, json={"display_name": label}))

    owner_id = checked(client.get("/api/me", headers=alice))["profile"]["id"]
    existing = checked(client.get(f"/api/listings?status=all&owner_id={owner_id}"))["listings"]
    titles = {listing["title"] for listing in existing}
    spots = checked(client.get("/api/meeting-spots"))["meeting_spots"]
    items = [
        {
            "title": "Navy suit — borrow preview (demo inventory)",
            "category": "formalwear", "allowed_modes": ["borrow"],
            "rental_fee_cents": 1500, "proposed_item_value_cents": 20000,
            "collateral_percent": 100, "condition": "good",
            "accessories": ["garment bag"], "known_defects": [],
            "specifications": {"jacket_size": "40R", "color": "navy"},
        },
        {
            "title": "Desk lamp — buy preview (demo inventory)",
            "category": "home", "allowed_modes": ["sale"],
            "sale_price_cents": 1800, "condition": None,
            "accessories": [], "known_defects": [],
        },
    ]
    for item in items:
        if item["title"] not in titles:
            checked(client.post("/api/listings", headers=alice, json={
                **item, "description": "Labeled sample inventory for an isolated local transaction preview.",
                "meeting_spot_ids": [spot["id"] for spot in spots],
            }))
    return app


def main():
    parser = argparse.ArgumentParser(description="Local sandbox preview of the transaction pages")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--data-dir", type=Path, default=PROJECT_ROOT / "var" / "exchange-preview")
    args = parser.parse_args()
    app = create_preview_app(args.data_dir)
    print("Local sandbox preview: demo identities, demo inventory, simulated payments.", flush=True)
    print(f"Open http://127.0.0.1:{args.port}/sign-in and choose Bob, then My exchanges.", flush=True)
    print("Choose Alice in a separate browser session to negotiate and accept.", flush=True)
    print(f"Isolated data: {args.data_dir.resolve()}", flush=True)
    app.run(host="127.0.0.1", port=args.port, debug=False)


if __name__ == "__main__":
    main()
