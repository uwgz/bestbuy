"""Settings read from the environment (Vercel → Settings → Environment Variables, or a local .env)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def database_url():
    """Neon gives postgres://… or postgresql://…; SQLAlchemy needs to be told to use psycopg 3.
    Without DATABASE_URL the site uses a small SQLite file (fine on your computer, temporary on Vercel)."""
    url = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or ""
    for prefix in ("postgres://", "postgresql://"):
        if url.startswith(prefix):
            return "postgresql+psycopg://" + url[len(prefix):]
    if url:
        return url
    folder = Path("/tmp") if os.environ.get("VERCEL") else ROOT / "instance"
    folder.mkdir(parents=True, exist_ok=True)
    return f"sqlite:///{folder / 'bestbuy.db'}"


def engine_options(url):
    if url.startswith("postgresql"):
        return {
            "pool_pre_ping": True,          # Neon closes idle connections: check before use
            "pool_recycle": 280,
            "connect_args": {"prepare_threshold": None},   # Neon's pooler (PgBouncer) can't keep prepared statements
        }
    return {}


def secret_key():
    """Signs the admin login cookie. Set SECRET_KEY on Vercel; without it, logins don't survive a restart."""
    key = os.environ.get("SECRET_KEY")
    if key:
        return key
    if not os.environ.get("VERCEL"):
        return "dev-only-not-secret"
    return os.urandom(32).hex()


class Config:
    SECRET_KEY = secret_key()
    SECRET_KEY_SET = bool(os.environ.get("SECRET_KEY")) or not os.environ.get("VERCEL")
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = bool(os.environ.get("VERCEL"))
    PERMANENT_SESSION_LIFETIME = 60 * 60 * 24 * 14      # the sign-in cookie lasts two weeks at most…
    ADMIN_IDLE_MINUTES = int(os.environ.get("ADMIN_IDLE_MINUTES", "15"))   # …but 15 minutes without activity signs you out
    TIMEZONE = os.environ.get("TIMEZONE", "Africa/Kigali")
    SQLALCHEMY_DATABASE_URI = database_url()
    SQLALCHEMY_ENGINE_OPTIONS = engine_options(SQLALCHEMY_DATABASE_URI)
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SEND_FILE_MAX_AGE_DEFAULT = 31536000      # static files carry ?v=<hash>, so browsers may keep them
    AUTO_LOAD_DEMO = os.environ.get("AUTO_LOAD_DEMO", "1") == "1"   # empty database → load the starting content
