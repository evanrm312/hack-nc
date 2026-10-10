"""Base configuration for the Flask application factory."""


class Config:
    """Defaults that can be overridden by create_app(test_config)."""

    TESTING = False
    SQLALCHEMY_DATABASE_URI = None
    SQLALCHEMY_TRACK_MODIFICATIONS = False
