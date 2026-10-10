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


class Config:
    """Default configuration. Values come from the environment."""

    SECRET_KEY = _env("SECRET_KEY", "dev-only-change-me")
    APP_ENV = _env("APP_ENV", "production")

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False

    # "supabase": verify bearer tokens against Supabase Auth (real email
    #             confirmation). Use this for the deployed app.
    # "sandbox":  explicitly labeled sandbox for local development/tests. Only
    #             the emails listed in SANDBOX_USERS are accepted. Never a
    #             public verification bypass.
    AUTH_MODE = (_env("AUTH_MODE", "sandbox") or "sandbox").lower()
    SANDBOX_USERS = _env_list("SANDBOX_USERS")
    ALLOWED_EMAIL_DOMAIN = (_env("ALLOWED_EMAIL_DOMAIN", "unc.edu") or "unc.edu").lower()

    SUPABASE_URL = _env("SUPABASE_URL")
    SUPABASE_ANON_KEY = _env("SUPABASE_ANON_KEY")
    SUPABASE_SERVICE_ROLE_KEY = _env("SUPABASE_SERVICE_ROLE_KEY")  # backend only
    AUTH_HTTP_TIMEOUT_SECONDS = float(_env("AUTH_HTTP_TIMEOUT_SECONDS", "5"))

    GEMINI_API_KEY = _env("GEMINI_API_KEY")  # backend only, used by Person 2

    # "local": files under UPLOAD_DIR/public and UPLOAD_DIR/private.
    # "supabase": interface defined, not implemented yet (see docs/tasks.md).
    STORAGE_BACKEND = (_env("STORAGE_BACKEND", "local") or "local").lower()
    UPLOAD_DIR = _env("UPLOAD_DIR", str(PROJECT_ROOT / "var" / "uploads"))
    MAX_UPLOAD_BYTES = int(_env("MAX_UPLOAD_BYTES", str(5 * 1024 * 1024)))
    MAX_CONTENT_LENGTH = MAX_UPLOAD_BYTES + 64 * 1024  # multipart overhead

    DISPLAY_TIMEZONE = "America/New_York"


def validate_config(config) -> None:
    """Fail fast on contradictory settings."""
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
    if config["STORAGE_BACKEND"] not in {"local", "supabase"}:
        raise RuntimeError("STORAGE_BACKEND must be 'local' or 'supabase'")
