import os
from datetime import timedelta
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent

try:
    from dotenv import load_dotenv
    load_dotenv(BASE_DIR / ".env")
except ImportError:
    pass

ON_VERCEL = bool(os.environ.get("VERCEL"))
MB = 1024 * 1024


def _blob_configured():
    return any(os.environ.get(k) for k in ("BLOB_READ_WRITE_TOKEN", "VERCEL_BLOB_READ_WRITE_TOKEN", "BLOB_STORE_ID"))


class Config:
    SECRET_KEY = os.environ.get("SECRET_KEY", "")
    INSTANCE_DIR = Path(os.environ.get("INSTANCE_DIR") or ("/tmp/best-buy-250" if ON_VERCEL else BASE_DIR / "instance"))
    DATABASE = INSTANCE_DIR / "vision.db"
    UPLOAD_DIR = INSTANCE_DIR / "uploads"


    DATABASE_URL = os.environ.get("DATABASE_URL") or os.environ.get("POSTGRES_URL") or ""

    MEDIA_STORAGE = os.environ.get("MEDIA_STORAGE") or ("blob" if _blob_configured() else "local")

    MAX_CONTENT_LENGTH = int(4.5 * MB if ON_VERCEL else 25 * MB) 
    UPLOAD_REQUEST_LIMIT = 4_000_000 if ON_VERCEL else 24 * MB
    MAX_IMAGE_SIDE = 1600
    STATIC_MAX_AGE = 60 * 60 * 24 * 365

    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = False
    PERMANENT_SESSION_LIFETIME = timedelta(hours=8)

    CSRF_ENABLED = True
    LOGIN_MAX_ATTEMPTS = 5 
    LOGIN_WINDOW_MINUTES = 15

class DevelopmentConfig(Config):
    DEBUG = True


class ProductionConfig(Config):
    SESSION_COOKIE_SECURE = True 


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
