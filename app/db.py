"""
Database connection handling and schema setup.

Local: a SQLite file in instance/. Online (Vercel): Turso, the hosted version of SQLite, when
TURSO_DATABASE_URL and TURSO_AUTH_TOKEN are set — same SQL, see app/turso.py.
"""
import sqlite3
from pathlib import Path

from flask import current_app, g


def using_turso(app=None):
    cfg = (app or current_app).config
    return bool(cfg.get("TURSO_DATABASE_URL") and cfg.get("TURSO_AUTH_TOKEN"))


def get_db():
    """One connection per request, rows behave like dicts."""
    if "db" not in g:
        if using_turso():
            from . import turso
            g.db = turso.connect(current_app.config["TURSO_DATABASE_URL"], current_app.config["TURSO_AUTH_TOKEN"])
        else:
            g.db = sqlite3.connect(current_app.config["DATABASE"])
            g.db.row_factory = sqlite3.Row
            g.db.execute("PRAGMA foreign_keys = ON")
    return g.db


def close_db(exc=None):
    db = g.pop("db", None)
    if db is not None:
        db.close()


def query(sql, args=(), one=False):
    rows = get_db().execute(sql, args).fetchall()
    return (rows[0] if rows else None) if one else rows


def execute(sql, args=()):
    db = get_db()
    cur = db.execute(sql, args)
    db.commit()
    return cur.lastrowid


def init_schema():
    schema = (Path(__file__).parent / "schema.sql").read_text()
    db = get_db()
    db.executescript(schema)
    db.commit()


def init_app(app):
    app.teardown_appcontext(close_db)
    # Create the tables on first start (safe to run every time). The site starts empty:
    # products, services, gear and photos are added from the admin panel.
    with app.app_context():
        init_schema()
