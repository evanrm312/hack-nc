"""Operator-only read-only diagnostics, safe even on an older schema."""
import os

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from flask import current_app

from .app import PROJECT_ROOT
from .catalog_import import target_identity
from .db import db
from .models import Listing


def backend_diagnostics():
    config = Config()
    config.set_main_option("script_location", str(PROJECT_ROOT / "migrations"))
    expected = sorted(ScriptDirectory.from_config(config).get_heads())
    names = ("DATABASE_URL", "SECRET_KEY", "SUPABASE_URL", "SUPABASE_ANON_KEY",
             "SUPABASE_SERVICE_ROLE_KEY", "GEMINI_API_KEY")
    report = dict(deployed_sha=os.environ.get("RENDER_GIT_COMMIT"),
                  app_env=current_app.config["APP_ENV"],
                  auth_mode=current_app.config["AUTH_MODE"],
                  environment_present={n: bool(os.environ.get(n)) for n in names},
                  expected_revisions=expected, ready=False)
    try:
        with db.engine.connect() as connection, connection.begin():
            if connection.dialect.name == "postgresql":
                connection.execute(text("SET TRANSACTION READ ONLY"))
            report["target"] = target_identity(connection)
            report["revisions"] = sorted(connection.execute(text("SELECT version_num FROM alembic_version")).scalars())
            report["counts"] = {table: connection.execute(text(f'SELECT count(*) FROM "{table}"')).scalar()
                               for table in ("profiles", "listings", "need_requests", "exchanges", "messages", "evidence", "reviews")}
            # Compile the deployed model query without inspecting any private values.
            connection.execute(db.select(Listing).limit(0))
            report["ready"] = report["revisions"] == expected
    except SQLAlchemyError as error:
        report["database_error"] = dict(type=type(error).__name__,
                                       sqlstate=getattr(getattr(error, "orig", None), "sqlstate", None))
    return report
