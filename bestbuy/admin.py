"""
Admin pages (/admin): sign in, then manage the shop.

Built so far: the layout, the login, Dashboard, Stock and Settings (admin_*.py files).
Orders and Giveaways show their page header until we design them.
"""
import re
import secrets
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for

from .extensions import db
from .models import AuditLog, Order, Product, User, local_today, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")

LOW_STOCK = 2          # this many units or fewer counts as "running low"
SHORT_WORDS = 4        # short name: up to 4 words
NAME_WORDS = 20        # full name: up to 20 words


class FormError(ValueError):
    """A mistake in what was typed; shown to the person as a message."""


# ======================================================================
#  Signing in
# ======================================================================
@bp.before_app_request
def _load_user():
    g.user = None
    uid = session.get("uid")
    if uid:
        user = db.session.get(User, uid)
        if user and user.is_active:
            g.user = user


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if not User.query.first():
                return redirect(url_for("admin.setup"))
            return redirect(url_for("admin.login", next=request.full_path.rstrip("?")))
        return view(*args, **kwargs)
    return wrapped


@bp.before_request
def _check_form_token():
    """Every admin form carries a secret token, so another website can't submit forms in your name."""
    if request.method == "POST":
        sent = request.form.get("csrf_token", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf_token", "")):
            abort(400, "This form expired. Go back, refresh the page and try again.")


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def audit(action, details=""):
    """Record who did what (see AuditLog)."""
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip())[:45]
    db.session.add(AuditLog(user_id=g.user.id if g.user else None, action=action, details=details, ip_address=ip))


def _sign_in(user):
    session.clear()
    session.permanent = True
    session["uid"] = user.id
    user.last_login_at = utcnow()
    audit("login", user.email)
    db.session.commit()


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First visit only: create the owner's account."""
    if User.query.first():
        return redirect(url_for("admin.login"))
    error = None
    if request.method == "POST":
        try:
            name = " ".join(request.form.get("name", "").split())
            email = request.form.get("email", "").strip().lower()
            password = request.form.get("password", "")
            if not name or not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
                raise FormError("Enter your name and a valid email address.")
            if len(password) < 8:
                raise FormError("Choose a password of at least 8 characters.")
            if password != request.form.get("confirm", ""):
                raise FormError("The two passwords are different.")
            user = User(name=name, email=email)
            user.set_password(password)
            db.session.add(user)
            db.session.flush()
            g.user = user
            _sign_in(user)
            flash(f"Welcome, {user.first_name}. Your admin is ready.", "success")
            return redirect(url_for("admin.stock"))
        except FormError as e:
            error = str(e)
    return render_template("admin/setup.html", error=error)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not User.query.first():
        return redirect(url_for("admin.setup"))
    if g.user:
        return redirect(url_for("admin.dashboard"))
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        if user and user.is_active and user.check_password(request.form.get("password", "")):
            g.user = user
            _sign_in(user)
            target = request.args.get("next", "")
            return redirect(target if target.startswith("/admin") else url_for("admin.dashboard"))
        error = "That email and password don't match."
    return render_template("admin/login.html", error=error,
                           key_missing=not current_app.config.get("SECRET_KEY_SET", True))


@bp.route("/logout", methods=["POST"])
def logout():
    session.clear()
    return redirect(url_for("admin.login"))


# ======================================================================
#  Layout: what the top bar and sidebar show on every page
# ======================================================================
@bp.context_processor
def _layout():
    if g.get("user") is None:
        return {"csrf_token": csrf_token}
    low = Product.query.filter(Product.stock <= LOW_STOCK).count()
    waiting = Order.query.filter_by(status="waiting").count()
    return {"low_stock": low, "new_orders": waiting, "admin_user": g.user.first_name, "csrf_token": csrf_token,
            "today": today().isoformat()}


def today():
    return local_today()


def _back(default):
    """After a pop-up form: back to the page it was opened from (filters kept)."""
    target = request.form.get("_back", "")
    return target if target.startswith("/admin") else default


def whole(value, label, low=0, high=100000):
    try:
        number = int(str(value).strip())
    except ValueError:
        raise FormError(f"{label}: enter a whole number.")
    if not low <= number <= high:
        raise FormError(f"{label}: between {low} and {high:,}.")
    return number


def amount(value, label, allow_zero=False):
    text = str(value or "").replace(",", "").replace(" ", "").strip()
    try:
        number = Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise FormError(f"{label}: enter an amount, like 1290000.")
    if number < 0 or number > Decimal("9999999999") or (number == 0 and not allow_zero):
        raise FormError(f"{label}: enter an amount, like 1290000.")
    return number


def text(f, name, label, required=True, limit=300):
    value = " ".join((f.get(name) or "").split())[:limit]
    if required and not value:
        raise FormError(f"Fill in {label}.")
    return value


def _page(title, subtitle, page_icon, button=None):
    return render_template("admin/page.html", title=title, subtitle=subtitle, page_icon=page_icon, button=button)


@bp.route("/orders")
@login_required
def orders():
    return _page("Orders", "Sales made in the shop and orders sent from the website.", "receipt")


# the pages live in their own files; importing them adds their routes to this blueprint
from . import admin_dashboard, admin_giveaways, admin_photography, admin_settings, admin_stock, admin_upload  # noqa: E402,F401
