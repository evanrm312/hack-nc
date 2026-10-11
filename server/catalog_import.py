"""Reviewed, targeted demo import. Never calls the broad development seed."""
from __future__ import annotations

import hashlib
import json
from io import BytesIO

from flask import current_app
from sqlalchemy import MetaData, Table, select, text

from .db import db
from .models import Listing, Profile
from .seed import _catalog_id
from .storage import get_storage

EXCLUDED = {"clothing-event-tablecloths", "dorm-storage-bins-pair"}
REQUIRED_REVISION = "c708communitymerge"


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, default=str,
                                     separators=(",", ":")).encode()).hexdigest()


def target_identity(connection):
    url = db.engine.url
    return {
        "driver": url.drivername, "host": url.host, "port": url.port,
        "database": url.database, "username": url.username,
        "schema": connection.execute(text("SELECT current_schema()")).scalar()
                  if connection.dialect.name == "postgresql" else "main",
        "storage_backend": current_app.config["STORAGE_BACKEND"],
        "supabase_url": current_app.config["SUPABASE_URL"],
        "public_bucket": current_app.config["SUPABASE_PUBLIC_BUCKET"],
    }


def _plan(connection, *, lock_rows=False):
    from fixtures.demo_catalog.validate_catalog import validate
    from fixtures.demo_catalog.validate_images import BASE, manifests, validate_images
    from .routes.catalog import _apply_listing_fields

    entries, owners, _ = validate()
    images = validate_images(entries)  # Missing licensed files or tampering refuse the job.
    if set(images["missing"]) != EXCLUDED or images["images"] != 52:
        raise ValueError("Import requires exactly the reviewed 52 licensed images")
    records = {r["listing_key"]: r for r in manifests()}
    # Reflection allows a read-only inventory before the existing schema is upgraded.
    meta = MetaData()
    profiles = Table("profiles", meta, autoload_with=connection)
    listings = Table("listings", meta, autoload_with=connection)
    revisions = sorted(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
    owner_rows, listing_rows = [], []
    for key, spec in sorted(owners.items()):
        owner_id = _catalog_id("owner", key)
        subject = f"sandbox:demo-catalog:v1:{key}"
        query = select(profiles).where(profiles.c.id == owner_id)
        existing = connection.execute(query.with_for_update() if lock_rows else query).mappings().first()
        by_subject = connection.execute(select(profiles.c.id).where(profiles.c.auth_subject == subject)).scalar()
        if by_subject is not None and by_subject != owner_id:
            raise ValueError(f"Demo owner subject collision: {key}")
        if existing and (not existing["is_demo"] or existing["verification_source"] != "sandbox"
                         or existing["auth_subject"] != subject):
            raise ValueError(f"Demo owner ID collision: {key}")
        values = dict(id=owner_id, auth_subject=subject, display_name=spec["display_name"],
                      confirmed_email_domain=current_app.config["ALLOWED_EMAIL_DOMAIN"],
                      verification_source="sandbox", is_demo=True)
        owner_rows.append(dict(key=key, id=owner_id, action="preserve" if existing else "insert",
                               before_sha256=digest(dict(existing)) if existing else None,
                               values=None if existing else values))

    for entry in sorted(entries, key=lambda e: e["key"]):
        key = entry["key"]
        if key in EXCLUDED:
            continue
        image = records[key]
        listing_id = _catalog_id("listing", key)
        owner_id = _catalog_id("owner", entry["owner_key"])
        notice = ("\n\nDEMO illustrative licensed reference photo; fictional inventory/provider, "
                  "not evidence of the listed model, size, condition, accessories or qualifications. "
                  + image["required_attribution"] + " Source: " + image["source_page_url"])
        candidate = Listing(id=listing_id, owner_id=owner_id, status="available",
                            publication_required=True, specifications={}, accessories=[],
                            known_defects=[], availability={}, meeting_spot_ids=[])
        body = {**entry["listing"], "description": entry["listing"]["description"] + notice}
        _apply_listing_fields(candidate, body, creating=True)
        values = {c.name: getattr(candidate, c.name) for c in Listing.__table__.columns
                  if c.name not in {"created_at", "updated_at"}}
        query = select(listings).where(listings.c.id == listing_id)
        existing = connection.execute(query.with_for_update() if lock_rows else query).mappings().first()
        action = "insert"
        if existing:
            if (existing["owner_id"] != owner_id or "demo" not in existing["title"].casefold()
                    or "DEMO" not in (existing["description"] or "")
                    or existing.get("club_id") is not None or existing.get("audience", "public") != "public"):
                raise ValueError(f"Demo listing collision or private audience: {key}")
            action = "preserve" if existing["public_photo_path"] else "fill_photo"
            if action == "fill_photo":
                if existing["status"] not in {"available", "withdrawn", "draft"} or existing["active_exchange_id"]:
                    raise ValueError(f"Existing demo listing is in an exchange: {key}")
                if image["required_attribution"] not in (existing["description"] or "") or "illustrative licensed reference" not in (existing["description"] or ""):
                    raise ValueError(f"Existing description needs reviewed photo attribution: {key}")
        listing_rows.append(dict(
            key=key, id=listing_id, owner_id=owner_id, action=action,
            before_sha256=digest(dict(existing)) if existing else None,
            values=values if action == "insert" else None,
            changes={"public_photo_path": "$validated_upload"} if action == "fill_photo" else {},
            image={**image, "local_filename": str((BASE / image["local_filename"]).relative_to(BASE))},
        ))
    inventory = dict(format_version=1, target=target_identity(connection),
                     revisions=revisions, required_revision=REQUIRED_REVISION,
                     excluded=sorted(EXCLUDED), owners=owner_rows, listings=listing_rows)
    return {**inventory, "plan_sha256": digest(inventory)}


def plan_import():
    """No DB/storage writes, including when the database is still at c707."""
    with db.engine.connect() as connection, connection.begin():
        if connection.dialect.name == "postgresql":
            connection.execute(text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ, READ ONLY"))
        return _plan(connection)


def apply_import(reviewed_plan):
    """One atomic import, fresh plan comparison, verified uploads, compensation."""
    if reviewed_plan.get("plan_sha256") != digest({k: v for k, v in reviewed_plan.items() if k != "plan_sha256"}):
        raise ValueError("Reviewed plan checksum is invalid")
    uploaded, storage = [], None
    try:
        with db.engine.begin() as connection:
            if connection.dialect.name == "postgresql":
                connection.execute(text("SELECT pg_advisory_xact_lock(708, 52)"))
            fresh = _plan(connection, lock_rows=True)
            if fresh != reviewed_plan:
                raise ValueError("Target, assets or records changed; review a new dry run")
            if fresh["revisions"] != [REQUIRED_REVISION]:
                raise ValueError("Apply requires the reviewed c708communitymerge migration first")
            if current_app.config["APP_ENV"] == "production" and current_app.config["STORAGE_BACKEND"] != "supabase":
                raise ValueError("Production import requires persistent Supabase storage")
            from fixtures.demo_catalog.validate_images import BASE
            storage = get_storage()
            paths = {}
            # Upload every needed object before publishing any row. Verify readback
            # through the public bucket; a provider ACK alone is insufficient.
            for row in fresh["listings"]:
                if row["action"] == "preserve":
                    continue
                data = (BASE / row["image"]["local_filename"]).read_bytes()
                if hashlib.sha256(data).hexdigest() != row["image"]["sha256"]:
                    raise ValueError("Asset changed after validation")
                stored = storage.save("public", BytesIO(data), current_app.config["MAX_UPLOAD_BYTES"])
                uploaded.append(stored.path)
                with current_app.test_request_context("/media/public/" + stored.path):
                    response = storage.send("public", stored.path, "image/webp")
                    try:
                        response.direct_passthrough = False
                        if response.status_code != 200 or hashlib.sha256(response.get_data()).hexdigest() != row["image"]["sha256"]:
                            raise ValueError("Public image readback validation failed")
                    finally:
                        response.close()
                paths[row["id"]] = stored.path
            for row in fresh["owners"]:
                if row["action"] == "insert":
                    connection.execute(Profile.__table__.insert().values(**row["values"]))
            for row in fresh["listings"]:
                if row["action"] == "insert":
                    connection.execute(Listing.__table__.insert().values(
                        **{**row["values"], "public_photo_path": paths[row["id"]]}))
                elif row["action"] == "fill_photo":
                    connection.execute(Listing.__table__.update().where(Listing.id == row["id"]).values(
                        public_photo_path=paths[row["id"]], updated_at=Listing.updated_at))
        return dict(inserted=sum(r["action"] == "insert" for r in fresh["listings"]),
                    photos_filled=sum(r["action"] == "fill_photo" for r in fresh["listings"]),
                    preserved=sum(r["action"] == "preserve" for r in fresh["listings"]))
    except Exception as error:
        cleanup_failed = []
        if storage is not None:
            for path in uploaded:
                try:
                    storage.delete("public", path)
                except Exception:
                    cleanup_failed.append(path)
        if cleanup_failed:
            # Generated public object paths are safe and necessary for operator cleanup.
            current_app.logger.error("Import rollback requires public object cleanup: %s", cleanup_failed)
            raise ValueError("Import rolled back; public object cleanup required (see sanitized log)") from None
        # Do not leak SQL, passwords, provider headers or payloads via CLI tracebacks.
        if isinstance(error, ValueError):
            raise
        raise ValueError(f"Import rolled back ({type(error).__name__}); uploads cleaned up") from None
