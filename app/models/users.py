"""Admin accounts (the shop owner and staff)."""
from werkzeug.security import check_password_hash, generate_password_hash

from ..db import execute, query

MIN_PASSWORD_LENGTH = 10


def count():
    return query("SELECT COUNT(*) AS n FROM users", one=True)["n"]


def get(user_id):
    return query("SELECT id, email, name, created_at, last_login_at FROM users WHERE id = ?", (user_id,), one=True)


def all_users():
    return query("SELECT id, email, name, created_at, last_login_at FROM users ORDER BY id")


def authenticate(email, password):
    row = query("SELECT * FROM users WHERE email = ?", ((email or "").strip(),), one=True)
    # always run a hash check so timing doesn't reveal whether the email exists
    hash_ = row["password_hash"] if row else generate_password_hash("not-a-real-password")
    ok = check_password_hash(hash_, password or "")
    return row if (row and ok) else None


def validate_password(password, confirm=None):
    if len(password or "") < MIN_PASSWORD_LENGTH:
        return f"Use at least {MIN_PASSWORD_LENGTH} characters for the password."
    if confirm is not None and password != confirm:
        return "The two passwords don't match."
    return None


def create(email, name, password):
    return execute(
        "INSERT INTO users (email, name, password_hash) VALUES (?, ?, ?)",
        (email.strip().lower(), name.strip(), generate_password_hash(password)),
    )


def set_password(user_id, password):
    execute("UPDATE users SET password_hash = ? WHERE id = ?", (generate_password_hash(password), user_id))


def check_password(user_id, password):
    row = query("SELECT password_hash FROM users WHERE id = ?", (user_id,), one=True)
    return bool(row) and check_password_hash(row["password_hash"], password or "")


def delete(user_id):
    execute("DELETE FROM users WHERE id = ?", (user_id,))


def touch_login(user_id):
    execute("UPDATE users SET last_login_at = datetime('now') WHERE id = ?", (user_id,))
