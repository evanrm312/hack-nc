"""Upgrade the actual predecessor revision in an isolated *_test schema."""
import pytest
from flask_migrate import upgrade
from sqlalchemy import MetaData, Table, inspect, text

from server.catalog_import import plan_import, apply_import
from server.db import db, utcnow
from tests.test_postgres_completion import isolated


def test_c707_upgrade_preserves_records_readiness_and_browser_isolation(tmp_path):
    with isolated(tmp_path) as app, app.app_context():
        app.config["MAX_UPLOAD_BYTES"] = 5 * 1024 * 1024
        upgrade(revision="c707browserroles")
        meta = MetaData()
        p = Table("profiles", meta, autoload_with=db.engine)
        l = Table("listings", meta, autoload_with=db.engine)
        req = Table("need_requests", meta, autoload_with=db.engine)
        db.session.execute(p.insert().values(id="old-owner", auth_subject="old-owner", display_name="Keep profile",
                           confirmed_email_domain="unc.edu", verification_source="supabase", is_demo=False, created_at=utcnow()))
        db.session.execute(l.insert().values(id="old-item", owner_id="old-owner", title="Existing item", description="Keep description",
                           category="electronics", specifications={"unknown": None}, accessories=[], known_defects=[],
                           allowed_modes=["sale"], sale_price_cents=1234, availability={}, meeting_spot_ids=[],
                           status="available", created_at=utcnow(), updated_at=utcnow()))
        db.session.execute(req.insert().values(id="old-request", requester_id="old-owner", original_text="Keep private schedule",
                           normalized={"category": "electronics"}, modes=["sale"], pickup_windows=[],
                           visibility="private", status="draft", created_at=utcnow(), updated_at=utcnow()))
        db.session.commit()
        before = {table.name: [dict(r) for r in db.session.execute(table.select()).mappings()] for table in (p, l, req)}
        db.session.remove()
        assert app.test_client().get("/api/ready").status_code == 503
        pre_upgrade = plan_import()
        assert pre_upgrade["revisions"] == ["c707browserroles"]
        with pytest.raises(ValueError, match="migration first"):
            apply_import(pre_upgrade)
        assert not list((tmp_path / "uploads").rglob("*.webp"))
        upgrade(revision="c708communitymerge")
        assert app.test_client().get("/api/ready").status_code == 200
        for table, rows in before.items():
            for row in rows:
                after = db.session.execute(text(f'SELECT * FROM "{table}" WHERE id=:id'), {"id": row["id"]}).mappings().one()
                assert all(after[key] == value for key, value in row.items())
        assert {"clubs", "club_memberships"} <= set(inspect(db.engine).get_table_names())
        schema = db.session.execute(text("SELECT current_schema()")).scalar()
        roles = db.session.execute(text("SELECT rolname FROM pg_roles WHERE rolname IN ('anon','authenticated')")).scalars().all()
        for role in roles:
            for table in ("clubs", "club_memberships", "messages", "evidence"):
                assert not db.session.execute(text("SELECT has_table_privilege(:role,:table,'SELECT,INSERT,UPDATE,DELETE')"),
                                              {"role": role, "table": schema + "." + table}).scalar()
                assert db.session.execute(text("SELECT relrowsecurity FROM pg_class WHERE oid=to_regclass(:table)"),
                                          {"table": schema + "." + table}).scalar()
        db.session.remove()
        with pytest.raises(ValueError, match="changed"):
            apply_import(pre_upgrade)
        assert apply_import(plan_import())["inserted"] == 52
        client = app.test_client()
        assert len(client.get("/api/listings").json["listings"]) == 53
        assert client.get("/api/recommendations").status_code == 200
        assert client.get("/api/requests/old-request").status_code in (401, 404)
        assert apply_import(plan_import())["preserved"] == 52
