"""Demo seed data. Everything here is labeled as demo/fixture data.

Creates (idempotently, keyed by stable auth_subject / titles):
- public meeting spots
- three sandbox demo profiles (Alice, Bob, Carol; verification_source="sandbox",
  is_demo=True) whose auth_subject matches what signing in as
  sandbox:<email> resolves to, so the seeded rows ARE the sign-in identities
- labeled demo inventory: Alice's navy suit (the seeded match), TI-84, and
  calculus tutoring service; Bob's desk lamp; Carol's intentionally
  incompatible 44L suit
- fixture PriceReference rows (is_fixture=True)

The catalog loader also adds 54 fixture listings with licensed reference photos.
No fabricated reviews, ratings,
exchanges, or survey answers. Running it again changes nothing that already
exists except the small in-place upgrades noted below.
"""

from __future__ import annotations

import hashlib
from datetime import date
from uuid import NAMESPACE_URL, uuid5
from pathlib import Path
from urllib.parse import urlparse

from flask import current_app
from sqlalchemy.engine import make_url

from .auth.identity import normalize_email
from .config import PROJECT_ROOT
from .db import db
from .models import Listing, MeetingSpot, PriceReference, Profile

# Earlier seeds created a separate "Demo Lender" identity nobody can sign in
# as. Its listings are withdrawn (never deleted: exchanges may reference them)
# so the demo inventory is not duplicated.
LEGACY_DEMO_LENDER_SUBJECT = "sandbox:demo-lender"
DEMO_LENDER_SUBJECT = LEGACY_DEMO_LENDER_SUBJECT

DEMO_SUIT_TITLE = "Navy suit, 40R (demo inventory)"
DEMO_INCOMPATIBLE_SUIT_TITLE = "Black suit, 44L (demo inventory, intentionally incompatible)"
DEMO_SUIT_AVAILABILITY = {
    "available_from": "2026-10-12T12:00:00Z",
    "available_until": "2026-10-16T22:00:00Z",
}

# Sign in as sandbox:<email>; the subject below is exactly what
# server/auth/identity.py derives for that email.
DEMO_USERS = [
    ("alice@unc.edu", "Alice (demo)"),
    ("bob@unc.edu", "Bob (demo)"),
    ("carol@unc.edu", "Carol (demo)"),
]


def sandbox_subject(email: str) -> str:
    digest = hashlib.sha256(normalize_email(email).encode("utf-8")).hexdigest()[:24]
    return f"sandbox:{digest}"


def validate_demo_seed_target(config, *, allow_supabase_postgres_dev: bool = False) -> None:
    """Refuse demo inserts outside a named development target or explicit opt-in."""
    if config.get("APP_ENV") != "development":
        raise ValueError("Demo seed requires APP_ENV=development")
    url = make_url(config["SQLALCHEMY_DATABASE_URI"])
    database = url.database or ""
    if url.get_backend_name() == "postgresql" and database.endswith("_dev"):
        return
    if allow_supabase_postgres_dev:
        supabase_host = urlparse(config.get("SUPABASE_URL") or "").hostname or ""
        project_ref = supabase_host.removesuffix(".supabase.co") if supabase_host.endswith(".supabase.co") else ""
        if (
            url.drivername == "postgresql+psycopg"
            and database == "postgres"
            and url.host
            and url.host.endswith(".pooler.supabase.com")
            and url.port == 5432
            and project_ref
            and "." not in project_ref
            and url.username == "postgres." + project_ref
        ):
            return
        raise ValueError("Supabase development seed opt-in requires the configured project's session pooler PostgreSQL URL ending in /postgres")
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


def _demo_listings(profiles: dict[str, Profile], spots: list[MeetingSpot]) -> list[tuple[Profile, dict]]:
    """(owner, Listing kwargs) for every demo row. Money is integer cents."""
    central = [s.id for s in spots[:2]]            # Union lobby, Davis Library
    south = [s.id for s in spots[1:3]]             # Davis Library, Rams Head
    alice, bob, carol = profiles["alice@unc.edu"], profiles["bob@unc.edu"], profiles["carol@unc.edu"]
    return [
        (alice, {
            "title": DEMO_SUIT_TITLE,
            "category": "formalwear",
            "description": "DEMO INVENTORY for the Campus Current prototype. Two-piece navy suit, 40R jacket with matching trousers; borrow only, free loan with a full-value deposit.",
            "specifications": {"type": "suit", "jacket_size": "40R", "color": "navy"},
            "condition": "good",
            "accessories": ["jacket", "pants"],
            "known_defects": [],
            "allowed_modes": ["borrow"],
            "sale_price_cents": None,
            "rental_fee_cents": 0,
            "proposed_item_value_cents": 20000,
            "collateral_percent": 100,
            "availability": {**DEMO_SUIT_AVAILABILITY, "notes": "Most weekdays after 2pm for pickup"},
            "meeting_spot_ids": central,
        }),
        (alice, {
            "title": "TI-84 graphing calculator (demo inventory)",
            "category": "electronics",
            "description": "DEMO INVENTORY. TI-84 Plus graphing calculator; borrow it for an exam week.",
            "specifications": {"type": "graphing calculator", "model": "TI-84 Plus"},
            "condition": "good",
            "accessories": ["USB cable"],
            "known_defects": [],
            "allowed_modes": ["borrow"],
            "sale_price_cents": None,
            "rental_fee_cents": 0,
            "proposed_item_value_cents": 8000,
            "collateral_percent": 100,
            "availability": {"available_from": None, "available_until": None, "notes": None},
            "meeting_spot_ids": central,
        }),
        (alice, {
            "title": "Calculus tutoring (demo inventory)",
            "category": "tutoring",
            "description": "DEMO INVENTORY. One-hour calculus tutoring sessions (MATH 231/232). Price is a simulated fee; nothing is charged.",
            "allowed_modes": ["service"],
            "service_price_cents": 2500,
            "service_duration_minutes": 60,
            "service_available_windows": [
                {"start": "2026-10-20T19:00:00Z", "end": "2026-10-20T22:00:00Z"},
                {"start": "2026-10-22T19:00:00Z", "end": "2026-10-22T22:00:00Z"},
            ],
            "specifications": {},
            "accessories": [],
            "known_defects": [],
            "availability": {},
            "meeting_spot_ids": [],
        }),
        (bob, {
            "title": "Desk lamp (demo inventory)",
            "category": "home",
            "description": "DEMO INVENTORY. Adjustable LED desk lamp, for sale.",
            "specifications": {"type": "desk lamp"},
            "condition": "good",
            "accessories": ["power adapter"],
            "known_defects": [],
            "allowed_modes": ["sale"],
            "sale_price_cents": 1000,
            "rental_fee_cents": None,
            "proposed_item_value_cents": None,
            "collateral_percent": None,
            "availability": {"available_from": None, "available_until": None, "notes": None},
            "meeting_spot_ids": central,
        }),
        (carol, {
            "title": DEMO_INCOMPATIBLE_SUIT_TITLE,
            "category": "formalwear",
            "description": "DEMO INVENTORY. Black suit, 44L; used to show a rejected match against a 40R request.",
            "specifications": {"type": "suit", "jacket_size": "44L", "color": "black"},
            "condition": "good",
            "accessories": ["garment bag"],
            "known_defects": [],
            "allowed_modes": ["sale", "borrow"],
            "sale_price_cents": 9000,
            "rental_fee_cents": 1500,
            "proposed_item_value_cents": 20000,
            "collateral_percent": 100,
            "availability": {"available_from": None, "available_until": None, "notes": None},
            "meeting_spot_ids": south,
        }),
    ]


def _stage_legacy_demo_data() -> list[str]:
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

    # ---- demo profiles (the sign-in identities themselves)
    sandbox_users = set(current_app.config.get("SANDBOX_USERS") or [])
    profiles: dict[str, Profile] = {}
    for email, display_name in DEMO_USERS:
        subject = sandbox_subject(email)
        profile = db.session.scalar(db.select(Profile).where(Profile.auth_subject == subject))
        if profile is None:
            profile = Profile(
                auth_subject=subject,
                display_name=display_name,
                confirmed_email_domain="unc.edu",
                verification_source="sandbox",
                is_demo=True,
            )
            db.session.add(profile)
            db.session.flush()
            out.append(f"demo profile created: {display_name}")
        if not profile.is_demo or profile.verification_source != "sandbox":
            raise ValueError("Demo sign-in profile collision")
        if email not in sandbox_users and any(line == f"demo profile created: {display_name}" for line in out):
            out.append(f"warning: {email} is not in SANDBOX_USERS, so nobody can sign in as {display_name} until it is added")
        profiles[email] = profile

    # ---- legacy "Demo Lender" rows from earlier seeds: withdraw, never delete
    legacy = db.session.scalar(db.select(Profile).where(Profile.auth_subject == LEGACY_DEMO_LENDER_SUBJECT))
    if legacy is not None:
        if not legacy.is_demo or legacy.verification_source != "sandbox":
            raise ValueError("Legacy demo lender subject collision")
        for listing in db.session.scalars(db.select(Listing).where(Listing.owner_id == legacy.id, Listing.status == "available")):
            listing.status = "withdrawn"
            out.append(f"legacy demo lender listing withdrawn: {listing.title}")

    # ---- demo inventory
    for owner, spec in _demo_listings(profiles, spots):
        exists = db.session.scalar(
            db.select(Listing).where(Listing.owner_id == owner.id, Listing.title == spec["title"])
        )
        if exists is None:
            db.session.add(Listing(owner_id=owner.id, **spec))
            out.append(f"demo listing created: {spec['title']} ({owner.display_name})")
            continue
        # Upgrade older demo rows in place. Never replace unrelated fields
        # or overwrite an explicit value a developer may have customized.
        if spec.get("specifications", {}).get("type") and "type" not in (exists.specifications or {}):
            exists.specifications = {**(exists.specifications or {}), "type": spec["specifications"]["type"]}
            out.append(f"demo listing type added: {spec['title']}")
        if spec["title"] == DEMO_SUIT_TITLE:
            availability = dict(exists.availability or {})
            missing_bounds = [key for key in DEMO_SUIT_AVAILABILITY if availability.get(key) is None]
            if missing_bounds:
                availability.update({key: DEMO_SUIT_AVAILABILITY[key] for key in missing_bounds})
                exists.availability = availability
                out.append("demo navy suit availability dates added")

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

    if not out:
        out.append("nothing to do; demo data already present")
    return out
# Stable namespace retained from the original reviewed catalog proposal.
def _catalog_id(kind: str, key: str) -> str:
    return uuid5(NAMESPACE_URL, f"campus-current:demo-catalog:v1:{kind}:{key}").hex


def _catalog_plan():
    """Validate fixtures, public-image provenance and collisions before writes."""
    from fixtures.demo_catalog.validate_catalog import validate
    from fixtures.demo_catalog.validate_images import manifests, validate_images
    from .auth.identity import resolve_identity
    from .routes.catalog import _apply_listing_fields

    entries, owners, _counts = validate()
    image_summary = validate_images(entries, allow_missing_files=True)
    images = {record["listing_key"]: record for record in manifests()}
    for key in image_summary["missing"]:
        images[key] = {**images[key], "status": "missing"}
    profiles, new_profiles, candidates = {}, [], []
    showcase = {"clothing-owner-1": "alice@unc.edu", "services-owner-1": "bob@unc.edu"}
    for key, spec in owners.items():
        namespaced = f"sandbox:demo-catalog:v1:{key}"
        identity = resolve_identity("sandbox:" + showcase[key], current_app.config) if key in showcase and current_app.config["AUTH_MODE"] == "sandbox" else None
        subject = identity.subject if identity else namespaced
        existing = db.session.scalar(db.select(Profile).where(Profile.auth_subject == subject))
        old = db.session.scalar(db.select(Profile).where(Profile.auth_subject == namespaced))
        collision = db.session.get(Profile, _catalog_id("owner", key))
        if old is not None and existing is not None and old is not existing:
            raise ValueError(f"Demo catalog showcase identity collision: {key}")
        profile = existing or old
        if collision is not None and collision is not profile:
            raise ValueError(f"Demo catalog profile ID collision: {key}")
        if profile is not None:
            if not profile.is_demo or profile.verification_source != "sandbox":
                raise ValueError(f"Demo catalog profile is not sandbox demo: {key}")
            # Authentication-created sandbox profiles are already visibly demo via
            # their public is_demo flag and sandbox badge. Preserve their names.
        else:
            profile = Profile(id=_catalog_id("owner", key), auth_subject=subject,
                display_name=spec["display_name"], confirmed_email_domain=current_app.config["ALLOWED_EMAIL_DOMAIN"],
                verification_source="sandbox", is_demo=True)
            new_profiles.append((key, profile))
        profiles[key] = (profile, subject)
    for entry in entries:
        profile, _subject = profiles[entry["owner_key"]]
        candidate = Listing(id=_catalog_id("listing", entry["key"]), owner_id=profile.id, status="available")
        body = dict(entry["listing"])
        image = images[entry["key"]]
        notice = ""
        if image.get("status") != "missing":
            notice = ("\n\nDEMO illustrative licensed reference photo; fictional inventory/provider, "
                "not evidence of the listed model, size, condition, accessories or qualifications. "
                + image["required_attribution"] + " Source: " + image["source_page_url"])
        body["description"] += notice
        _apply_listing_fields(candidate, body, creating=True)
        existing = db.session.get(Listing, candidate.id)
        if existing is not None:
            if (existing.owner_id != profile.id or "demo" not in existing.title.casefold()
                    or "DEMO" not in (existing.description or "")):
                raise ValueError(f"Demo catalog listing collision: {entry['key']}")
        image = dict(image)
        if existing is not None and notice and image["required_attribution"] not in (existing.description or ""):
            body["description"] = (existing.description or "") + notice
            _apply_listing_fields(candidate, body, creating=True)
            image["seed_description"] = body["description"]
        candidates.append((entry["key"], existing or candidate, existing is None, image))
    return profiles, new_profiles, candidates


def seed_demo_data(*, allow_supabase_postgres_dev: bool = False) -> list[str]:
    """Seed the protected development target; never overwrite customized rows.

    Missing reference photos and storage failures are nonfatal. Newly saved
    objects are deleted if the database transaction cannot complete.
    """
    from .storage import get_storage

    validate_demo_seed_target(current_app.config, allow_supabase_postgres_dev=allow_supabase_postgres_dev)
    uploaded = []
    storage = None
    try:
        profiles, new_profiles, candidates = _catalog_plan()
        out = []
        for key, profile in new_profiles:
            db.session.add(profile)
            out.append(f"demo catalog profile created: {key}")
        for profile, subject in profiles.values():
            # Upgrade only the same labeled demo profile from the old namespace.
            if profile.auth_subject != subject:
                profile.auth_subject = subject
                out.append("demo catalog showcase authentication mapped")
        db.session.flush()
        for key, listing, is_new, image in candidates:
            if is_new:
                db.session.add(listing)
                out.append(f"demo catalog listing created: {key}")
            if image.get("status") == "missing":
                if is_new:
                    out.append(f"demo catalog reference missing: {key}")
                continue
            if listing.public_photo_path:
                continue
            path = (PROJECT_ROOT / "fixtures" / "demo_catalog" / image["local_filename"])
            try:
                if storage is None:
                    storage = get_storage()
                with path.open("rb") as stream:
                    stored = storage.save("public", stream, current_app.config["MAX_UPLOAD_BYTES"])
                uploaded.append(stored.path)
                listing.public_photo_path = stored.path
                if image.get("seed_description"):
                    listing.description = image["seed_description"]
                out.append(f"demo catalog photo saved: {key}")
            except Exception:
                # Neither exception text nor credentials/storage headers are logged.
                current_app.logger.warning("Demo catalog public photo storage failed: %s", key)
                out.append(f"demo catalog photo unavailable: {key}")
        out.extend(_stage_legacy_demo_data())
        db.session.commit()
        return out or ["nothing to do; demo data already present"]
    except Exception:
        db.session.rollback()
        if storage is not None:
            for path in uploaded:
                try:
                    storage.delete("public", path)
                except Exception:
                    current_app.logger.warning("Demo catalog rollback photo cleanup failed")
        raise
