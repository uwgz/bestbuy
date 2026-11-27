"""
Best Buy 250. create_app() builds the Flask app: database, pages, commands.
The pages read everything from the database (see models.py).
"""
import hashlib
import os

from flask import Flask

from .config import ROOT, Config
from .extensions import db

STATIC = ROOT / "public" / "static"


def create_app(overrides=None):
    app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static",
                template_folder=str(ROOT / "templates"))
    app.config.from_object(Config)
    app.config.update(overrides or {})

    db.init_app(app)

    from . import commands, pages
    pages.init_app(app)
    commands.init_app(app)
    _version_static_links(app)

    with app.app_context():
        from . import models  # noqa: F401  (registers the tables)
        db.create_all()                      # makes any missing tables; never changes existing ones
        if app.config.get("AUTO_LOAD_DEMO"):
            _load_demo_if_empty()
    return app


def _load_demo_if_empty():
    """First start on an empty database: copy in the starting content so the site isn't blank."""
    from sqlalchemy.exc import IntegrityError
    from .models import Product
    from .seed import load_demo
    if Product.query.first():
        return
    try:
        added = load_demo()
        if added:
            print("Loaded starting content:", ", ".join(added))
    except IntegrityError:            # two servers started at once and the other one did it first
        db.session.rollback()


def _version_static_links(app):
    """Add ?v=<file hash> to /static links, so a new version is never hidden by an old cached copy."""
    versions = {}

    @app.url_defaults
    def add_version(endpoint, values):
        if endpoint == "static" and "filename" in values and "v" not in values:
            name = values["filename"]
            if name not in versions:
                try:
                    versions[name] = hashlib.md5((STATIC / name).read_bytes()).hexdigest()[:10]
                except OSError:
                    versions[name] = (os.environ.get("VERCEL_DEPLOYMENT_ID") or "1")[:10]
            values["v"] = versions[name]
