"""
Security helpers:
- CSRF tokens on every form (blocks forged submissions from other sites)
- admin sign-in session and @login_required
- throttling of repeated failed sign-ins
"""
import hmac
import secrets
import time
from collections import defaultdict, deque
from functools import wraps

from flask import abort, current_app, g, redirect, request, session, url_for
from markupsafe import Markup

from .models import users


# ---------- CSRF ----------
def csrf_token():
    if "_csrf" not in session:
        session["_csrf"] = secrets.token_urlsafe(32)
    return session["_csrf"]


def csrf_field():
    return Markup(f'<input type="hidden" name="_csrf" value="{csrf_token()}">')


def _check_csrf():
    if request.method != "POST" or not current_app.config.get("CSRF_ENABLED", True):
        return
    sent = request.form.get("_csrf") or request.headers.get("X-CSRF-Token", "")
    if not sent or not hmac.compare_digest(sent, session.get("_csrf", "")):
        abort(400, "Your session expired. Please go back, refresh the page and try again.")


# ---------- Sign-in ----------
def login_user(user):
    session.clear()                      # new session id → prevents session fixation
    session.permanent = True
    session["user_id"] = user["id"]
    users.touch_login(user["id"])


def logout_user():
    session.clear()


def _load_user():
    uid = session.get("user_id")
    g.user = users.get(uid) if uid else None


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.get("user") is None:
            return redirect(url_for("admin.login", next=request.full_path if request.method == "GET" else None))
        return view(*args, **kwargs)
    return wrapped


# ---------- Failed sign-in throttling (per IP, in memory) ----------
_failures = defaultdict(deque)


def _client_ip():
    return request.headers.get("X-Forwarded-For", request.remote_addr or "?").split(",")[0].strip()


def too_many_attempts():
    window = current_app.config["LOGIN_WINDOW_MINUTES"] * 60
    q = _failures[_client_ip()]
    while q and q[0] < time.time() - window:
        q.popleft()
    return len(q) >= current_app.config["LOGIN_MAX_ATTEMPTS"]


def record_failure():
    _failures[_client_ip()].append(time.time())


def clear_failures():
    _failures.pop(_client_ip(), None)


def init_app(app):
    app.before_request(_load_user)
    app.before_request(_check_csrf)
    app.jinja_env.globals["csrf_token"] = csrf_token
    app.jinja_env.globals["csrf_field"] = csrf_field

    @app.after_request
    def security_headers(resp):
        resp.headers.setdefault("X-Content-Type-Options", "nosniff")
        resp.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        resp.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
        if request.blueprint == "admin":
            resp.headers["X-Robots-Tag"] = "noindex, nofollow"
            resp.headers["Cache-Control"] = "no-store"
        return resp
