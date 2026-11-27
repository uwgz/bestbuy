"""Terminal commands:   flask --app app <command>"""
import click

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
