"""Person 1 HTTP routes: /api/me, /api/listings, /api/requests, /api/meeting-spots, pages."""

from flask import Flask


def register_blueprints(app: Flask) -> None:
    from ..exchanges.routes import bp as exchanges_bp
    from .catalog import bp as catalog_bp
    from .health import health_bp
    from .me import bp as me_bp
    from .pages import bp as pages_bp
    from .requests import bp as requests_bp

    from .notifications import bp as notifications_bp
    from .. import notifications  # transactional event listener
    from .discovery import bp as discovery_bp
    app.register_blueprint(discovery_bp)
    from .locations import bp as locations_bp
    from .community import bp as community_bp
    from .profiles import bp as profiles_bp
    app.register_blueprint(profiles_bp)
    app.register_blueprint(community_bp)
    app.register_blueprint(locations_bp)
    app.register_blueprint(notifications_bp)
    app.register_blueprint(me_bp)
    app.register_blueprint(catalog_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(requests_bp)
    app.register_blueprint(exchanges_bp)
    app.register_blueprint(pages_bp)
