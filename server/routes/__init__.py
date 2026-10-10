"""Person 1 HTTP routes: /api/me, /api/listings, /api/requests, /api/meeting-spots, pages."""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from ..exchanges.routes import bp as exchanges_bp
    from .catalog import bp as catalog_bp
    from .me import bp as me_bp
    from .pages import bp as pages_bp
    from .requests import bp as requests_bp

    app.register_blueprint(me_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(requests_bp)
    app.register_blueprint(exchanges_bp)
    app.register_blueprint(pages_bp)
