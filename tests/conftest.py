"""Shared, isolated Flask test fixtures."""

import pytest
from flask_migrate import upgrade

from server.app import create_app


@pytest.fixture
def app():
    return create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": None})


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def db_app(tmp_path):
    """Apply the real migration to a fresh temporary database per test."""
    database_path = tmp_path / "catalog_test.sqlite"
    app = create_app({
        "TESTING": True,
        "SQLALCHEMY_DATABASE_URI": f"sqlite:///{database_path}",
    })
    with app.app_context():
        upgrade()
    return app


@pytest.fixture
def db_client(db_app):
    return db_app.test_client()
