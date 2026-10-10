"""Explicit, development-only demo inventory."""

import os
from pathlib import Path
from uuid import NAMESPACE_URL, uuid5

import click
from flask import current_app
from flask.cli import with_appcontext
from sqlalchemy.engine import make_url
from sqlalchemy.exc import SQLAlchemyError

from server.db import db
from server.models import Listing, Profile

DEMO_PROFILE_ID = "demo-m2-profile"
DEMO_LISTING_ID = str(uuid5(NAMESPACE_URL, "campus-current/m2/demo-suit"))


def _is_dedicated_dev_database(uri):
    url = make_url(uri)
    database = url.database or ""
    if url.get_backend_name() == "postgresql":
        return database.endswith("_dev")
    if url.get_backend_name() == "sqlite" and database != ":memory:":
        return Path(database).stem.endswith("_dev")
    return False


@click.command("seed-demo")
@with_appcontext
def seed_demo():
    """Insert clearly marked demo listings into a dedicated dev database."""
    uri = current_app.config.get("SQLALCHEMY_DATABASE_URI")
    if os.environ.get("APP_ENV") != "development" or not uri:
        raise click.ClickException(
            "Demo seed requires APP_ENV=development and DATABASE_URL."
        )
    if not _is_dedicated_dev_database(uri):
        raise click.ClickException(
            "Demo seed requires a dedicated database with a name ending in _dev."
        )

    try:
        if db.session.get(Profile, DEMO_PROFILE_ID) is None:
            db.session.add(Profile(
                id=DEMO_PROFILE_ID,
                display_name="DEMO: Campus Current lender",
                confirmed_email_domain=None,
            ))
        if db.session.get(Listing, DEMO_LISTING_ID) is None:
            db.session.add(Listing(
                id=DEMO_LISTING_ID,
                owner_id=DEMO_PROFILE_ID,
                title="DEMO: Interview suit",
                category="Clothing",
                description="Fictional inventory for local development only.",
                specifications={"size": "medium", "color": "navy"},
                condition="Good; fictional demo item.",
                accessories=["jacket", "trousers"],
                mode="borrow",
                rental_fee_cents=1500,
                proposed_item_value_cents=20000,
                collateral_percent=100,
                status="active",
                is_demo=True,
            ))
        db.session.commit()
    except SQLAlchemyError as exc:
        db.session.rollback()
        raise click.ClickException("Demo seed failed; check migrations and database access.") from exc

    click.echo("Demo profile and listing are present.")
