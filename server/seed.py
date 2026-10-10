"""Demo seed data. Everything here is labeled as demo/fixture data.

Creates (idempotently, keyed by stable auth_subject / labels):
- public meeting spots
- a demo lender profile (verification_source="sandbox", is_demo=True)
- the seeded suit listing and one intentionally incompatible listing
- fixture PriceReference rows (is_fixture=True)
"""

from __future__ import annotations

from datetime import date
from pathlib import Path

from sqlalchemy.engine import make_url

from .config import PROJECT_ROOT
from .db import db
from .models import Listing, MeetingSpot, PriceReference, Profile

DEMO_LENDER_SUBJECT = "sandbox:demo-lender"


def validate_demo_seed_target(config) -> None:
    """Refuse demo inserts outside an explicitly named development database."""
    if config.get("APP_ENV") != "development":
        raise ValueError("Demo seed requires APP_ENV=development")
    url = make_url(config["SQLALCHEMY_DATABASE_URI"])
    database = url.database or ""
    if url.get_backend_name() == "postgresql" and database.endswith("_dev"):
        return
    if url.get_backend_name() == "sqlite" and database != ":memory:":
        path = Path(database)
        if path.resolve() == (PROJECT_ROOT / "var" / "dev.sqlite3").resolve():
            return
        if path.stem.endswith("_dev"):
            return
    raise ValueError("Demo seed requires a dedicated development database")

MEETING_SPOTS = [
    ("Student Union main lobby", "Pit / Union", "Open 7am-midnight; staffed info desk."),
    ("Davis Library front entrance", "Central campus", "Well lit; library hours posted at door."),
    ("Rams Head Plaza", "South campus", "Outdoor public plaza; daylight meetups recommended."),
]


def seed_demo_data() -> list[str]:
    out: list[str] = []

    spots: list[MeetingSpot] = []
    for label, area, notes in MEETING_SPOTS:
        spot = db.session.scalar(db.select(MeetingSpot).where(MeetingSpot.label == label))
        if spot is None:
            spot = MeetingSpot(label=label, public_area=area, access_notes=notes)
            db.session.add(spot)
            out.append(f"meeting spot created: {label}")
        spots.append(spot)
    db.session.flush()

    lender = db.session.scalar(db.select(Profile).where(Profile.auth_subject == DEMO_LENDER_SUBJECT))
    if lender is None:
        lender = Profile(
            auth_subject=DEMO_LENDER_SUBJECT,
            display_name="Demo Lender (demo account)",
            confirmed_email_domain="unc.edu",
            verification_source="sandbox",
            is_demo=True,
        )
        db.session.add(lender)
        db.session.flush()
        out.append("demo lender profile created")

    demo_listings = [
        {
            "title": "Navy suit, 40R (demo inventory)",
            "category": "formalwear",
            "description": "DEMO INVENTORY for the Campus Current prototype. Two-piece navy suit, 40R jacket, 33x32 trousers.",
            "specifications": {"jacket_size": "40R", "trouser_waist": 33, "trouser_inseam": 32, "color": "navy"},
            "condition": "good",
            "accessories": ["garment bag"],
            "known_defects": [],
            "allowed_modes": ["borrow", "sale"],
            "sale_price_cents": 9000,
            "rental_fee_cents": 1500,
            "proposed_item_value_cents": 20000,
            "collateral_percent": 100,
            "availability": {"available_from": None, "available_until": None, "notes": "Most weekdays after 2pm"},
        },
        {
            "title": "Charcoal suit, 46L (demo inventory, intentionally incompatible)",
            "category": "formalwear",
            "description": "DEMO INVENTORY. Oversized 46L suit used to show a rejected match.",
            "specifications": {"jacket_size": "46L", "trouser_waist": 40, "trouser_inseam": 34, "color": "charcoal"},
            "condition": "fair",
            "accessories": [],
            "known_defects": ["missing one cuff button"],
            "allowed_modes": ["borrow"],
            "sale_price_cents": None,
            "rental_fee_cents": 0,
            "proposed_item_value_cents": 12000,
            "collateral_percent": 100,
            "availability": {"available_from": None, "available_until": None, "notes": None},
        },
    ]
    for spec in demo_listings:
        exists = db.session.scalar(
            db.select(Listing).where(Listing.owner_id == lender.id, Listing.title == spec["title"])
        )
        if exists is None:
            db.session.add(Listing(owner_id=lender.id, meeting_spot_ids=[s.id for s in spots[:2]], **spec))
            out.append(f"demo listing created: {spec['title']}")

    fixtures = [
        dict(
            category="formalwear",
            specifications={"type": "two-piece suit"},
            condition="good",
            price_type="sale",
            duration_basis=None,
            lower_cents=6000,
            upper_cents=15000,
            sample_count=12,
            source="FIXTURE: hand-labeled demo range, not observed platform transactions",
            observed_from=date(2026, 8, 1),
            observed_to=date(2026, 9, 30),
            is_fixture=True,
            version=1,
        ),
        dict(
            category="formalwear",
            specifications={"type": "two-piece suit"},
            condition="good",
            price_type="rental",
            duration_basis="per_3_days",
            lower_cents=1000,
            upper_cents=3000,
            sample_count=8,
            source="FIXTURE: hand-labeled demo range, not observed platform transactions",
            observed_from=date(2026, 8, 1),
            observed_to=date(2026, 9, 30),
            is_fixture=True,
            version=1,
        ),
    ]
    for spec in fixtures:
        exists = db.session.scalar(
            db.select(PriceReference).where(
                PriceReference.category == spec["category"],
                PriceReference.price_type == spec["price_type"],
                PriceReference.version == spec["version"],
                PriceReference.is_fixture.is_(True),
            )
        )
        if exists is None:
            db.session.add(PriceReference(**spec))
            out.append(f"fixture price reference created: {spec['category']} {spec['price_type']}")

    db.session.commit()
    if not out:
        out.append("nothing to do; demo data already present")
    return out
