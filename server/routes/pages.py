"""HTML page routes. Templates are owned by Person 1 (auth/), Person 3
(base.html, marketplace/), and Person 4 (exchanges/). Only public, browser-safe
config is passed to templates (never service-role or Gemini keys)."""

from __future__ import annotations

from flask import Blueprint, current_app, render_template

bp = Blueprint("pages", __name__)


def _public_config() -> dict:
    cfg = current_app.config
    return {
        "auth_mode": cfg["AUTH_MODE"],
        "sandbox_users": cfg["SANDBOX_USERS"] if cfg["AUTH_MODE"] == "sandbox" else [],
        "supabase_url": cfg["SUPABASE_URL"] if cfg["AUTH_MODE"] == "supabase" else None,
        "supabase_anon_key": cfg["SUPABASE_ANON_KEY"] if cfg["AUTH_MODE"] == "supabase" else None,
        "allowed_email_domain": cfg["ALLOWED_EMAIL_DOMAIN"],
        "require_email_confirmation": cfg["REQUIRE_EMAIL_CONFIRMATION"],
    }


@bp.app_context_processor
def _inject_public_config():
    return {"public_config": _public_config()}


@bp.get("/")
def home():
    return render_template("marketplace/home.html")


@bp.get("/sign-in")
def sign_in():
    return render_template("auth/sign_in.html")


@bp.get("/results/<request_id>")
def results(request_id: str):
    return render_template("marketplace/results.html", request_id=request_id)


@bp.get("/listings/new")
def listing_form():
    return render_template("marketplace/listing_form.html")


@bp.get("/listings/<listing_id>")
def listing_detail(listing_id: str):
    return render_template("marketplace/listing_detail.html", listing_id=listing_id)


@bp.get("/requests")
def requests_feed():
    return render_template("marketplace/requests_feed.html")


@bp.get("/exchanges")
def my_exchanges():
    return render_template("exchanges/my_exchanges.html")


@bp.get("/exchanges/<exchange_id>")
def exchange_room(exchange_id: str):
    return render_template("exchanges/room.html", exchange_id=exchange_id)


@bp.get("/profiles/<profile_id>")
def profile_page(profile_id):
    return render_template("marketplace/profile.html", profile_id=profile_id)

@bp.get("/about")
def about():
    return render_template("about.html")
