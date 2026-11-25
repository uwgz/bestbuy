"""
Command-line tasks:
    flask --app run create-admin      create a sign-in account
    flask --app run reset-password    set a new password for an account
    flask --app run init-db           create the database tables
"""
import click
from flask import current_app

from .models import users


def init_app(app):
    @app.cli.command("create-admin")
    @click.option("--email", prompt=True)
    @click.option("--name", prompt=True)
    @click.password_option()
    def create_admin(email, name, password):
        """Create an admin account."""
        error = users.validate_password(password)
        if error:
            raise click.ClickException(error)
        users.create(email, name, password)
        click.echo(f"Admin account created for {email}. Sign in at /altar/login")

    @app.cli.command("reset-password")
    @click.option("--email", prompt=True)
    @click.password_option()
    def reset_password(email, password):
        """Set a new password for an existing account."""
        from .db import query
        row = query("SELECT id FROM users WHERE email = ?", (email.strip().lower(),), one=True)
        if not row:
            raise click.ClickException("No account with that email.")
        error = users.validate_password(password)
        if error:
            raise click.ClickException(error)
        users.set_password(row["id"], password)
        click.echo("Password updated.")

    @app.cli.command("init-db")
    def init_db():
        """Create database tables (safe to run again)."""
        from .db import init_schema
        init_schema()
        click.echo(f"Database ready at {current_app.config['DATABASE']}")
