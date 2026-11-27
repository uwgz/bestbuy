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
        _rename_columns()
        _add_new_columns()
        _update_checks()
        if app.config.get("AUTO_LOAD_DEMO"):
            _load_demo_if_empty()
            _add_starting_gear_once()
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
    ("products", "discount_until", "DATE"),
]


# Columns renamed after their table was made: (table, old name, new name)
RENAMED_COLUMNS = [("gear_items", "price_usd", "price_cad")]


def _rename_columns():
    from sqlalchemy import inspect, text
    inspector = inspect(db.engine)
    for table, old, new in RENAMED_COLUMNS:
        if table in inspector.get_table_names():
            names = {c["name"] for c in inspector.get_columns(table)}
            if old in names and new not in names:
                try:
                    with db.engine.begin() as conn:
                        conn.execute(text(f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}"))
                except Exception:        # another server renamed it at the same moment
                    pass


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


# Rules (CHECK constraints) that grew after their table was made: (table, name, rule)
CHECKS = [
    ("stock_moves", "ck_stock_moves_kind", "kind IN ('added', 'refill', 'sale', 'return', 'loss', 'giveaway')"),
]


def _update_checks():
    """Replace a rule on an existing PostgreSQL table when it was widened (e.g. a new kind of stock move)."""
    if db.engine.dialect.name != "postgresql":
        return
    from sqlalchemy import text
    for table, name, rule in CHECKS:
        try:
            with db.engine.begin() as conn:
                current = conn.execute(text("SELECT pg_get_constraintdef(oid) FROM pg_constraint WHERE conname = :n"), {"n": name}).scalar()
                if current and "giveaway" not in current:
                    conn.execute(text(f"ALTER TABLE {table} DROP CONSTRAINT {name}"))
                    conn.execute(text(f"ALTER TABLE {table} ADD CONSTRAINT {name} CHECK ({rule})"))
        except Exception:                # another server changed it at the same moment
            pass


def _add_starting_gear_once():
    """The Gear list came after the site went live: add the starting gear one time.
    A setting remembers it, so gear you remove later never comes back."""
    from sqlalchemy.exc import IntegrityError
    from .models import GearItem, Setting
    from .seed import GEAR, gear_rows
    if db.session.get(Setting, "gear_seeded"):
        return
    try:
        if not GearItem.query.first():
            db.session.add_all(gear_rows())
            print(f"Added {len(GEAR)} starting gear items.")
        db.session.add(Setting(key="gear_seeded", value="1"))
        db.session.commit()
    except IntegrityError:               # another server did it at the same moment
        db.session.rollback()


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
