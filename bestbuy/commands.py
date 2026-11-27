"""Terminal commands:   flask --app app <command>"""
import click
from sqlalchemy import text

from .extensions import db


def init_app(app):
    @app.cli.command("create-tables")
    def create_tables():
        """Make any missing tables (the site also does this when it starts)."""
        db.create_all()
        click.echo("Tables are ready.")

    @app.cli.command("load-demo")
    def load_demo_command():
        """Copy the starting content into empty tables (tables with rows are left alone)."""
        from .seed import load_demo
        added = load_demo()
        click.echo("Added: " + ", ".join(added) if added else "Nothing added: every table already has content.")

    @app.cli.command("delete-old-site")
    def delete_old_site():
        """Delete, for good, the earlier site's tables (kept in the old_site schema)."""
        from . import OLD_SCHEMA
        if db.engine.dialect.name != "postgresql":
            click.echo("This is only for the Neon (PostgreSQL) database: set DATABASE_URL first.")
            return
        with db.engine.connect() as conn:
            tables = [r[0] for r in conn.execute(text(
                "SELECT table_name FROM information_schema.tables WHERE table_schema = :s ORDER BY table_name"),
                {"s": OLD_SCHEMA})]
        if not tables:
            click.echo("Nothing to delete: there are no old tables.")
            return
        host = db.engine.url.host
        click.echo(f"Database: {host}")
        click.echo(f"Old tables in '{OLD_SCHEMA}' ({len(tables)}): " + ", ".join(tables))
        click.echo("The new site's tables are not touched.")
        if not click.confirm("Delete these old tables and all their data for good?", default=False):
            click.echo("Cancelled. Nothing was deleted.")
            return
        with db.engine.begin() as conn:
            conn.execute(text(f"DROP SCHEMA {OLD_SCHEMA} CASCADE"))
        click.echo(f"Deleted {len(tables)} old tables.")
