"""Flask application factory."""

import os

from flask import Flask, jsonify, request

from server.config import Config
from server.db import db, migrate
from server import models  # noqa: F401 - register model metadata for migrations
from server.routes.catalog import catalog_bp
from server.routes.health import health_bp
from server.seed import seed_demo


def create_app(test_config=None):
    """Create and configure a new application instance."""
    app = Flask(__name__)
    app.config.from_object(Config)
    app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get("DATABASE_URL")
    if test_config is not None:
        app.config.update(test_config)

    if app.config.get("SQLALCHEMY_DATABASE_URI"):
        db.init_app(app)
    migrate.init_app(app, db)

    app.register_blueprint(health_bp)
    app.register_blueprint(catalog_bp)
    app.cli.add_command(seed_demo)

    @app.errorhandler(404)
    def not_found(error):
        if request.path == "/api" or request.path.startswith("/api/"):
            return jsonify({
                "error": {
                    "code": "not_found",
                    "message": "API route not found.",
                    "fields": {},
                }
            }), 404
        return error

    return app
