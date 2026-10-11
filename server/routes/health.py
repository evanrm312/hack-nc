"""HTTP availability endpoint."""

from flask import Blueprint, jsonify

health_bp = Blueprint("health", __name__, url_prefix="/api")


@health_bp.get("/health")
def health():
    return jsonify({"status": "ok"})


@health_bp.get("/ready")
def ready():
    from sqlalchemy import text
    from sqlalchemy.exc import SQLAlchemyError
    from alembic.config import Config
    from alembic.script import ScriptDirectory
    from pathlib import Path
    from ..db import db
    config=Config()
    config.set_main_option('script_location',str(Path(__file__).resolve().parents[2]/'migrations'))
    expected=ScriptDirectory.from_config(config).get_current_head()
    try:
        with db.engine.connect() as connection:
            connection.execute(text('SELECT 1'))
            revision=connection.execute(text('SELECT version_num FROM alembic_version')).scalar()
        available=revision==expected
    except SQLAlchemyError:
        available=False
    response=jsonify(status='ready' if available else 'unavailable')
    response.status_code=200 if available else 503
    response.headers['Cache-Control']='no-store'
    return response
