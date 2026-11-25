"""
Application settings.

Values come from environment variables (or a `.env` file, see `.env.example`),
with safe defaults for local development.

Hosting on Vercel (detected from the VERCEL variable Vercel sets):
  * the code folder is read-only, so working files go to /tmp
  * photos go to Vercel Blob when a Blob store is connected (BLOB_READ_WRITE_TOKEN / BLOB_STORE_ID)
  * the database is Neon (PostgreSQL) when DATABASE_URL is set to its connection string
  * one request can carry at most 4.5 MB, so photo uploads are kept under that
"""
import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

try:  # load .env if python-dotenv is installed
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:  # pragma: no cover
    pass

ON_VERCEL = bool(os.environ.get("VERCEL"))
MB = 1024 * 1024


def _blob_configured():
    return any(os.environ.get(k) for k in ("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN", "BLOB_STORE_ID"))


class Config:
    # Leave SECRET_KEY empty in development: one is generated and kept in instance/secret_key.
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    INSTANCE_DIR = Path(os.environ.get("INSTANCE_DIR") or ("/tmp/vision-electronics" if ON_VERCEL else BASE_DIR / "instance"))
    DATABASE = INSTANCE_DIR / "vision.db"
    UPLOAD_DIR = INSTANCE_DIR / "uploads"          # photos added from the admin panel (local storage)

    # Database: Neon / PostgreSQL when DATABASE_URL is a postgresql://… address, otherwise the
    # local SQLite file above. (Vercel's Neon integration sets DATABASE_URL by itself.)
    DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or ""

    # Photos: "local" (instance/uploads) or "blob" (Vercel Blob, needs a *public* Blob store)
    MEDIA_STORAGE = os.environ.get("MEDIA_STORAGE") or ("blob" if _blob_configured() else "local")

    MAX_CONTENT_LENGTH = int(4.5 * MB if ON_VERCEL else 25 * MB)   # per request
    UPLOAD_REQUEST_LIMIT = 4_000_000 if ON_VERCEL else 24 * MB   # checked in the browser before sending (Vercel max: 4.5 MB)
    MAX_IMAGE_SIDE = 1600                          # uploaded photos are resized to this
    STATIC_MAX_AGE = 60 * 60 * 24 * 365            # static files carry ?v=<hash>, so they can be cached for a year

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)  # admin stays signed in for a working day

    CSRF_ENABLED = True                            # every form carries a secret token
    LOGIN_MAX_ATTEMPTS = 5                         # failed sign-ins allowed ...
    LOGIN_WINDOW_MINUTES = 15                      # ... within this many minutes


class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True                   # requires HTTPS


class TestingConfig(Config):
    TESTING = True
    SECRET_KEY = "test-secret"
    CSRF_ENABLED = False
    DATABASE_URL = ""
    MEDIA_STORAGE = "local"


CONFIGS = {
    "development": DevelopmentConfig,
    "production": ProductionConfig,
    "testing": TestingConfig,
}
