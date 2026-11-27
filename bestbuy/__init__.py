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

    from . import admin, commands, pages
    pages.init_app(app)
    app.register_blueprint(admin.bp)
    commands.init_app(app)
    _version_static_links(app)

    with app.app_context():
        from . import models  # noqa: F401  (registers the tables)
        _move_old_site_tables()
        db.create_all()                      # makes any missing tables; never changes existing ones
        _add_new_columns()
        if app.config.get("AUTO_LOAD_DEMO"):
            _load_demo_if_empty()
    return app


# Tables of the earlier version of the site (the one with /altar). Same names, different columns.
OLD_SITE_TABLES = ("giveaway_wins", "giveaways", "studio_gear", "messages", "bookings", "settings", "portfolio",
                   "service_images", "services", "product_images", "sales", "products", "users",
                   # made by a first start that then failed on the old tables (product_photos even points at the
                   # old products table): set aside too, so they are made again properly
                   "product_photos", "categories", "portfolio_items", "hero_slides")
OLD_SCHEMA = "old_site"


def _move_old_site_tables():
    """A Neon database used by the earlier version still has its tables, and their names clash with the new ones.
    Move them, untouched with all their data, into a separate schema called old_site. Runs once; nothing is deleted.
    (Moving keeps their indexes and ID counters with them, so the new tables can use the plain names.)"""
    if db.engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text
    with db.engine.begin() as conn:
        conn.execute(text("SELECT pg_advisory_xact_lock(250250)"))      # one server at a time
        old_layout = conn.execute(text(
            "SELECT 1 FROM information_schema.columns WHERE table_schema = current_schema() "
            "AND table_name = 'products' AND column_name = 'short_name'")).first()
        if not old_layout:
            return
        conn.execute(text(f"CREATE SCHEMA IF NOT EXISTS {OLD_SCHEMA}"))
        for name in OLD_SITE_TABLES:
            conn.execute(text(f'ALTER TABLE IF EXISTS "{name}" SET SCHEMA {OLD_SCHEMA}'))
    print(f"Moved the earlier site's tables into the '{OLD_SCHEMA}' schema (nothing deleted).")


# Columns added after their table was first made: (table, column, SQL type and default)
NEW_COLUMNS = [
    ("products", "cost", "NUMERIC(12, 2) NOT NULL DEFAULT 0"),
    ("order_items", "unit_cost", "NUMERIC(12, 2) NOT NULL DEFAULT 0"),
]


def _add_new_columns():
    """create_all() never changes a table that exists, so add new columns to existing tables here."""
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    for table, column, kind in NEW_COLUMNS:
        if table in inspector.get_table_names() and column not in {c["name"] for c in inspector.get_columns(table)}:
            try:
                with db.engine.begin() as conn:
                    conn.execute(text(f'ALTER TABLE {table} ADD COLUMN {column} {kind}'))
            except Exception:            # another server added it at the same moment
                pass


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
