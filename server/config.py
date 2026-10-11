"""Application configuration loaded from environment variables.

Copy .env.example to .env for local development. Backend-only secrets
(SUPABASE_SERVICE_ROLE_KEY, GEMINI_API_KEY, SECRET_KEY) must never be
rendered into templates or JavaScript. Only SUPABASE_URL and
SUPABASE_ANON_KEY are safe to expose to the browser.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    return value


def _env_list(name: str) -> list[str]:
    raw = _env(name, "") or ""
    return [item.strip().lower() for item in raw.split(",") if item.strip()]


def _database_url() -> str:
    """Relative sqlite paths are resolved against the project root (Flask-SQLAlchemy
    would otherwise put them under the instance folder)."""
    url = _env("DATABASE_URL", "sqlite:///var/dev.sqlite3") or ""
    prefix = "sqlite:///"
    if url.startswith(prefix):
        path = url[len(prefix):]
        if path and path != ":memory:" and not Path(path).is_absolute():
            url = prefix + (PROJECT_ROOT / path).as_posix()
    return url


def engine_options(uri):
    return ({"pool_pre_ping": True, "pool_size": int(_env("DB_POOL_SIZE", "4")), "max_overflow": 0,
        "pool_timeout": 10, "pool_recycle": 300, "connect_args": {"connect_timeout": 5, "options": "-c statement_timeout=15000 -c lock_timeout=5000"}} if uri.startswith("postgresql") else {})


class Config:
    """Default configuration. Values come from the environment."""

    SECRET_KEY = _env("SECRET_KEY", "dev-only-change-me")
    # Fail closed when a deployment forgets to set its environment marker.
    # Local setup copies .env.example, which explicitly selects development.
    APP_ENV = _env("APP_ENV", "production")

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = engine_options(_database_url())
    TRUSTED_PROXY_HOPS = int(_env("TRUSTED_PROXY_HOPS", "0"))
    RATE_LIMIT_ENABLED = APP_ENV == "production"
    NORMALIZE_RATE_PER_MINUTE = int(_env("NORMALIZE_RATE_PER_MINUTE", "10"))
    WRITE_RATE_PER_MINUTE = int(_env("WRITE_RATE_PER_MINUTE", "60"))
    SESSION_COOKIE_SECURE = APP_ENV == "production"
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"

    # "supabase": verify bearer tokens against Supabase Auth (real email
    #             confirmation). Use this for the deployed app.
    # "sandbox":  explicitly labeled sandbox for local development/tests. Only
    #             the emails listed in SANDBOX_USERS are accepted. Never a
    #             public verification bypass.
    AUTH_MODE = (_env("AUTH_MODE", "sandbox") or "sandbox").lower()
    SANDBOX_USERS = _env_list("SANDBOX_USERS")
    ALLOWED_EMAIL_DOMAIN = (_env("ALLOWED_EMAIL_DOMAIN", "unc.edu") or "unc.edu").lower()
    # Temporary operator-controlled testing exception; fail closed by default.
    REQUIRE_EMAIL_CONFIRMATION = (_env("REQUIRE_EMAIL_CONFIRMATION", "true") or "true").lower() != "false"

    SUPABASE_URL = _env("SUPABASE_URL")
    SUPABASE_ANON_KEY = _env("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")  # backend only
    AUTH_HTTP_TIMEOUT_SECONDS = float(_env("AUTH_HTTP_TIMEOUT_SECONDS", "5"))

    GEMINI_API_KEY = _env("GEMINI_API_KEY")  # backend only, used by Person 2

    # "local": files under UPLOAD_DIR/public and UPLOAD_DIR/private.
    # "supabase": server-side uploads to separate public/private buckets.
    STORAGE_BACKEND = (_env("STORAGE_BACKEND", "local") or "local").lower()
    SUPABASE_PUBLIC_BUCKET = _env("SUPABASE_PUBLIC_BUCKET", "public-listings")
    SUPABASE_PRIVATE_BUCKET = _env("SUPABASE_PRIVATE_BUCKET", "private-evidence")
    STORAGE_HTTP_TIMEOUT_SECONDS = float(_env("STORAGE_HTTP_TIMEOUT_SECONDS", "10"))
    UPLOAD_DIR = _env("UPLOAD_DIR", str(PROJECT_ROOT / "var" / "uploads"))
    MAX_UPLOAD_BYTES = int(_env("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES + 64 * 1024  # multipart overhead

    DISPLAY_TIMEZONE = "America/New_York"


def validate_config(config) -> None:
    """Fail fast on contradictory settings."""
    if config["APP_ENV"] not in {"development", "production"}:
        raise RuntimeError("APP_ENV must be 'development' or 'production'")
    if config.get("TRUSTED_PROXY_HOPS", 0) not in (0,1):
        raise RuntimeError("TRUSTED_PROXY_HOPS must be 0 or 1; trust only an isolated reverse proxy")
    if min(config.get("NORMALIZE_RATE_PER_MINUTE",10),config.get("WRITE_RATE_PER_MINUTE",60)) < 1:
        raise RuntimeError("Rate limits must be positive")
    pool_size=config.get("SQLALCHEMY_ENGINE_OPTIONS",{}).get("pool_size",4)
    if not 1 <= pool_size <= 16:
        raise RuntimeError("DB_POOL_SIZE must be between 1 and 16")
    mode = config["AUTH_MODE"]
    if mode not in {"supabase", "sandbox"}:
        raise RuntimeError(f"AUTH_MODE must be 'supabase' or 'sandbox', got {mode!r}")
    if mode == "sandbox" and not config["SANDBOX_USERS"]:
        raise RuntimeError(
            "AUTH_MODE=sandbox requires SANDBOX_USERS (comma-separated seeded emails). "
            "The sandbox is an isolated, labeled mode, not a public bypass."
        )
    if mode == "supabase" and not (config["SUPABASE_URL"] and config["SUPABASE_ANON_KEY"]):
        raise RuntimeError("AUTH_MODE=supabase requires SUPABASE_URL and SUPABASE_ANON_KEY")
    if config["APP_ENV"] == "production":
        if mode != "supabase":
            raise RuntimeError("APP_ENV=production requires AUTH_MODE=supabase")
        if not config["SECRET_KEY"] or len(config["SECRET_KEY"]) < 32 or config["SECRET_KEY"] in {"dev-only-change-me", "change-me", "REPLACE_WITH_RANDOM_SECRET"}:
            raise RuntimeError("APP_ENV=production requires a unique SECRET_KEY of at least 32 characters")
        if not config["SQLALCHEMY_DATABASE_URI"].startswith("postgresql+psycopg://"):
            raise RuntimeError("APP_ENV=production requires postgresql+psycopg DATABASE_URL")
    if config["STORAGE_BACKEND"] not in {"local", "supabase"}:
        raise RuntimeError("STORAGE_BACKEND must be 'local' or 'supabase'")
    if config["STORAGE_BACKEND"] == "supabase":
        if not config["SUPABASE_URL"] or not config["SUPABASE_SERVICE_ROLE_KEY"]:
            raise RuntimeError("STORAGE_BACKEND=supabase requires SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY")
        if not config["SUPABASE_PUBLIC_BUCKET"] or not config["SUPABASE_PRIVATE_BUCKET"] or config["SUPABASE_PUBLIC_BUCKET"] == config["SUPABASE_PRIVATE_BUCKET"]:
            raise RuntimeError("Supabase public and private storage buckets must be distinct")
