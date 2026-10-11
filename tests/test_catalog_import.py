"""Targeted operator import, retries, failure compensation and privacy."""
import json
from pathlib import Path

import pytest
from flask import Response
from sqlalchemy import event, select, func

from server.catalog_import import plan_import, apply_import, EXCLUDED, digest
from server.db import db
from server.models import Listing, Profile
from server.seed import _catalog_id
from server.storage import LocalStorage
from tests.test_catalog import _migrated_app


@pytest.fixture
def import_app(tmp_path):
    app, _ = _migrated_app(tmp_path, "import_dev.sqlite")
    app.config["MAX_UPLOAD_BYTES"] = 5 * 1024 * 1024
    return app


def counts():
    return [db.session.scalar(select(func.count()).select_from(model)) for model in (Profile, Listing)]


def files(app):
    return sorted(Path(app.config["UPLOAD_DIR"]).rglob("*.webp"))


def test_dry_run_and_cli_are_read_only_exact_and_secret_free(import_app, monkeypatch):
    monkeypatch.setattr("server.catalog_import.get_storage", lambda: pytest.fail("dry run must not access storage"))
    with import_app.app_context():
        before = counts()
        plan = plan_import()
        assert len(plan["listings"]) == 52 and len(plan["owners"]) == 12
        assert set(plan["excluded"]) == EXCLUDED
        assert counts() == before and files(import_app) == []
        assert plan == plan_import()
        assert all(r["id"] == _catalog_id("listing", r["key"]) for r in plan["listings"])
        assert all(r["image"]["sha256"] and r["image"]["license_url"] for r in plan["listings"])
    result = import_app.test_cli_runner().invoke(args=["import-demo-catalog", "--dry-run"])
    assert result.exit_code == 0 and json.loads(result.output) == plan
    for name in ("SECRET_KEY", "SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY"):
        secret = import_app.config.get(name)
        if secret:
            assert secret not in result.output
    refused = import_app.test_cli_runner().invoke(args=["import-demo-catalog", "--apply"])
    assert refused.exit_code != 0 and "--plan" in refused.output


def test_import_and_retry_preserve_existing_records_and_images(import_app, tmp_path):
    with import_app.app_context():
        owner = Profile(auth_subject="existing-real", display_name="Keep name", confirmed_email_domain="unc.edu",
                        verification_source="supabase", is_demo=False)
        db.session.add(owner); db.session.flush()
        unrelated = Listing(owner_id=owner.id, title="Existing item", description="Keep exactly", category="electronics",
                            allowed_modes=["sale"], sale_price_cents=1234)
        db.session.add(unrelated); db.session.commit()
        before = unrelated.to_dict()
        plan = plan_import()
        # Roundtrip the exact operator JSON used by --apply.
        plan = json.loads(json.dumps(plan))
        assert apply_import(plan) == dict(inserted=52, photos_filled=0, preserved=0)
        db.session.expire_all()
        assert counts() == [13, 53]
        assert db.session.get(Listing, unrelated.id).to_dict() == before
        navy = db.session.get(Listing, _catalog_id("listing", "clothing-navy-suit-40r"))
        navy.sale_price_cents = 777; navy.status = "withdrawn"
        db.session.commit(); before_navy = navy.to_dict()
        before_files = files(import_app)
        assert len(before_files) == 52
        assert apply_import(plan_import()) == dict(inserted=0, photos_filled=0, preserved=52)
        db.session.expire_all()
        assert navy.to_dict() == before_navy and files(import_app) == before_files
        assert all(db.session.get(Listing, _catalog_id("listing", key)) is None for key in EXCLUDED)
        rows = db.session.scalars(select(Listing).where(Listing.id != unrelated.id)).all()
        assert all(r.audience == "public" and r.club_id is None and r.publication_required for r in rows)
        assert all(r.owner.is_demo and r.owner.verification_source == "sandbox" for r in rows)
        urls = [r.to_dict()["public_photo_url"] for r in rows]
    client = import_app.test_client()
    assert all(client.get(url).status_code == 200 for url in urls)
    # A fresh dry run uses current records, so no duplicate rows or uploads occur.
    path = tmp_path / "reviewed.json"
    with import_app.app_context():
        path.write_text(json.dumps(plan_import()))
    result = import_app.test_cli_runner().invoke(args=["import-demo-catalog", "--apply", "--plan", str(path)])
    assert result.exit_code == 0 and json.loads(result.output)["preserved"] == 52


@pytest.mark.parametrize("failure", ["save", "readback", "database"])
def test_failed_import_publishes_nothing_cleans_uploads_and_retries(import_app, monkeypatch, failure):
    storage = LocalStorage(import_app.config["UPLOAD_DIR"])
    original_save = storage.save
    calls = []
    def save(*args):
        calls.append(True)
        if failure == "save" and len(calls) == 3:
            raise RuntimeError("private secret must not be logged")
        return original_save(*args)
    monkeypatch.setattr(storage, "save", save)
    if failure == "readback":
        monkeypatch.setattr(storage, "send", lambda *a: Response(b"corrupt", mimetype="image/webp"))
    monkeypatch.setattr("server.catalog_import.get_storage", lambda: storage)
    with import_app.app_context():
        plan = plan_import()
        def broken_insert(connection, cursor, statement, parameters, context, executemany):
            if statement.startswith("INSERT INTO listings"):
                raise RuntimeError("secret SQL parameters must not leak")
        engine = db.engine
        if failure == "database":
            event.listen(engine, "before_cursor_execute", broken_insert)
        try:
            with pytest.raises(ValueError) as error:
                apply_import(plan)
        finally:
            if failure == "database":
                event.remove(engine, "before_cursor_execute", broken_insert)
        assert "secret" not in str(error.value)
        assert counts() == [0, 0] and files(import_app) == []
        monkeypatch.setattr("server.catalog_import.get_storage", lambda: LocalStorage(import_app.config["UPLOAD_DIR"]))
        assert apply_import(plan)["inserted"] == 52


def test_stale_target_or_records_and_invalid_checksum_refused_before_upload(import_app, monkeypatch):
    monkeypatch.setattr("server.catalog_import.get_storage", lambda: pytest.fail("stale plan must not upload"))
    with import_app.app_context():
        plan = plan_import()
        altered = {**plan, "target": {**plan["target"], "public_bucket": "different"}}
        with pytest.raises(ValueError, match="checksum"):
            apply_import(altered)
        altered["plan_sha256"] = digest({k: v for k, v in altered.items() if k != "plan_sha256"})
        with pytest.raises(ValueError, match="changed"):
            apply_import(altered)
        assert counts() == [0, 0]


def test_fill_photo_preserves_description_price_and_status(import_app):
    with import_app.app_context():
        apply_import(plan_import())
        row = db.session.get(Listing, _catalog_id("listing", "clothing-navy-suit-40r"))
        row.public_photo_path = None
        row.description += " Customized words to retain."
        row.rental_fee_cents = 999; row.status = "withdrawn"
        db.session.commit()
        before = {c.name: getattr(row, c.name) for c in Listing.__table__.columns}
        result = apply_import(plan_import())
        db.session.expire_all()
        assert result == dict(inserted=0, photos_filled=1, preserved=51)
        after = {c.name: getattr(row, c.name) for c in Listing.__table__.columns}
        assert after["public_photo_path"]
        after["public_photo_path"] = before["public_photo_path"]
        assert before == after


def test_stale_record_and_real_owner_collision_refuse_before_upload(import_app, monkeypatch):
    with import_app.app_context():
        apply_import(plan_import())
        plan = plan_import()
        row = db.session.get(Listing, _catalog_id("listing", "clothing-navy-suit-40r"))
        row.rental_fee_cents = 876
        db.session.commit()
        monkeypatch.setattr("server.catalog_import.get_storage", lambda: pytest.fail("changed record must not upload"))
        with pytest.raises(ValueError, match="changed"):
            apply_import(plan)
        row.owner.is_demo = False; row.owner.verification_source = "supabase"
        db.session.commit()
        with pytest.raises(ValueError, match="owner ID collision"):
            plan_import()


def test_private_club_collision_is_never_made_public(import_app):
    with import_app.app_context():
        apply_import(plan_import())
        from server.models import Club
        club = Club(name="Private club", slug="private-test", code_hash="test-only-hash")
        db.session.add(club); db.session.flush()
        row = db.session.get(Listing, _catalog_id("listing", "clothing-navy-suit-40r"))
        row.club_id = club.id; row.audience = "club"
        db.session.commit()
        before_files = files(import_app)
        with pytest.raises(ValueError, match="private audience"):
            plan_import()
        assert files(import_app) == before_files
        assert row.audience == "club"
    assert import_app.test_client().get(f"/api/listings/{row.id}").status_code == 404


def test_asset_failure_refuses_before_writes(import_app, monkeypatch):
    def invalid(*a, **k):
        raise ValueError("invalid hash/license/missing licensed file")
    monkeypatch.setattr("fixtures.demo_catalog.validate_images.validate_images", invalid)
    with import_app.app_context():
        with pytest.raises(ValueError, match="invalid hash"):
            plan_import()
        assert counts() == [0, 0] and files(import_app) == []


def test_cleanup_failure_reports_generated_public_objects(import_app, monkeypatch, caplog):
    storage = LocalStorage(import_app.config["UPLOAD_DIR"])
    monkeypatch.setattr(storage, "send", lambda *a: Response(b"invalid"))
    def broken_delete(*a):
        raise RuntimeError("secret provider header")
    monkeypatch.setattr(storage, "delete", broken_delete)
    monkeypatch.setattr("server.catalog_import.get_storage", lambda: storage)
    with import_app.app_context():
        with pytest.raises(ValueError, match="cleanup required"):
            apply_import(plan_import())
        assert counts() == [0, 0]
        assert files(import_app)[0].name in caplog.text
        assert "secret provider header" not in caplog.text
