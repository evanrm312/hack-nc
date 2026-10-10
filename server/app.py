"""Flask application factory and CLI commands.

    flask --app server.app run          # dev server
    flask --app server.app db upgrade   # apply migrations
    flask --app server.app seed-demo    # meeting spots + labeled demo inventory
    gunicorn wsgi:app                   # production
"""

from __future__ import annotations

from pathlib import Path

import click
from flask import Flask

from .config import Config, validate_config
from .db import db, migrate
from .errors import register_error_handlers

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def create_app(overrides: dict | None = None) -> Flask:
    app = Flask(
        __name__,
        template_folder=str(PROJECT_ROOT / "templates"),
        static_folder=str(PROJECT_ROOT / "static"),
    )
    app.config.from_object(Config)
    if overrides:
        app.config.update(overrides)
    validate_config(app.config)

    if app.config["SQLALCHEMY_DATABASE_URI"].startswith("sqlite:///"):
        db_file = app.config["SQLALCHEMY_DATABASE_URI"].removeprefix("sqlite:///")
        if db_file and db_file != ":memory:":
            Path(db_file).parent.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"], "public").mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"], "private").mkdir(parents=True, exist_ok=True)

    db.init_app(app)
    migrate.init_app(app, db, directory=str(PROJECT_ROOT / "migrations"))

    from . import models  # noqa: F401  (register tables with SQLAlchemy)
    from .routes import register_blueprints

    register_error_handlers(app)
    register_blueprints(app)
    _register_cli(app)

    @app.get("/healthz")
    def healthz():
        return {"ok": True, "auth_mode": app.config["AUTH_MODE"]}

    return app


def _register_cli(app: Flask) -> None:
    @app.cli.command("seed-demo")
    def seed_demo():
        """Insert meeting spots, a labeled demo lender, demo inventory, and fixture price ranges."""
        from .seed import seed_demo_data

        summary = seed_demo_data()
        for line in summary:
            click.echo(line)
