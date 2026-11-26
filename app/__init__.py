"""
Best Buy 250 — electronics store and photography studio.

Application factory: `create_app()` builds and configures the Flask app.
"""
import os
import secrets
from pathlib import Path

from flask import Flask, send_from_directory

from config import BASE_DIR, CONFIGS, ON_VERCEL

# CSS, JS, icons and images live in public/static: on Vercel the CDN serves public/ directly,
# and locally Flask serves the same folder at the same /static/… addresses.
STATIC_DIR = BASE_DIR / "public" / "static"


def create_app(config_name=None, **overrides):
    config_name = config_name or os.environ.get("FLASK_ENV_NAME") or ("production" if ON_VERCEL else "development")
    app = Flask(__name__, static_folder=str(STATIC_DIR), static_url_path="/static")
    app.config.from_object(CONFIGS[config_name])
    app.config.update(overrides)
    app.config["SEND_FILE_MAX_AGE_DEFAULT"] = app.config["STATIC_MAX_AGE"]

    instance = Path(app.config["INSTANCE_DIR"])
    if "DATABASE" not in overrides:
        app.config["DATABASE"] = instance / "vision.db"
    if "UPLOAD_DIR" not in overrides:
        app.config["UPLOAD_DIR"] = instance / "uploads"
    instance.mkdir(parents=True, exist_ok=True)
    Path(app.config["UPLOAD_DIR"]).mkdir(parents=True, exist_ok=True)
    _ensure_secret_key(app, instance)

    from . import db, security, helpers, cli
    db.init_app(app)
    security.init_app(app)
    helpers.init_app(app)
    cli.init_app(app)

    from .blueprints.main import bp as main_bp
    from .blueprints.shop import bp as shop_bp
    from .blueprints.studio import bp as studio_bp
    from .blueprints.admin import bp as admin_bp
    app.register_blueprint(main_bp)
    app.register_blueprint(shop_bp)
    app.register_blueprint(studio_bp)
    app.register_blueprint(admin_bp, url_prefix="/altar")   # admin area: /altar/login

    @app.route("/media/<path:filename>")
    def media(filename):
        """Photos uploaded from the admin panel (stored outside the code, in instance/uploads)."""
        return send_from_directory(app.config["UPLOAD_DIR"], filename, max_age=60 * 60 * 24 * 30)

    # files at the top of public/ (Vercel serves them itself; this covers running locally)
    @app.route("/favicon.ico")
    @app.route("/robots.txt")
    def public_root_file():
        from flask import request
        return send_from_directory(BASE_DIR / "public", request.path.lstrip("/"), max_age=86400)

    _version_static_urls(app)

    from . import errors
    errors.init_app(app)
    return app


def _version_static_urls(app):
    """url_for('static', …) adds ?v=<content hash>: files can be cached for a year, and a changed
    file gets a new address straight away."""
    import hashlib
    cache = {}

    @app.url_defaults
    def add_version(endpoint, values):
        if endpoint != "static" or "v" in values or "filename" not in values:
            return
        name = values["filename"]
        if name not in cache or app.debug:
            try:
                cache[name] = hashlib.md5((STATIC_DIR / name).read_bytes()).hexdigest()[:10]
            except OSError:
                cache[name] = None
        if cache[name]:
            values["v"] = cache[name]


def _ensure_secret_key(app, instance):
    """Use SECRET_KEY from the environment, or generate one once and keep it in instance/."""
    if app.config.get("SECRET_KEY"):
        return
    if ON_VERCEL and not app.testing:
        # every Vercel instance has its own /tmp: a generated key would sign people out at random
        raise RuntimeError("Set SECRET_KEY in Vercel → Project → Settings → Environment Variables.")
    key_file = instance / "secret_key"
    if not key_file.exists():
        key_file.write_text(secrets.token_hex(32))
        key_file.chmod(0o600)
    app.config["SECRET_KEY"] = key_file.read_text().strip()
