"""
Admin pages (/admin): sign in, then manage the shop.

Signing in: email + password, or the five security questions (admin_account.py). Five wrong tries in a row
lock the account for 15 minutes. 15 minutes without activity signs you out (ADMIN_IDLE_MINUTES).
Roles (models.ROLES): owner = everything; manager = everything except Employees and Settings;
employee = Sell, Refill and Return / loss in Stock, and giveaway codes. See can().
The pages live in admin_*.py files.
"""
import re
import secrets
import time
from datetime import timedelta, timezone
from decimal import Decimal, InvalidOperation
from functools import wraps

from flask import Blueprint, abort, current_app, flash, g, redirect, render_template, request, session, url_for

from .extensions import db
from .models import AuditLog, GiveawayCode, Order, Product, User, local_today, utcnow

bp = Blueprint("admin", __name__, url_prefix="/admin")

LOW_STOCK = 2          # this many units or fewer counts as "running low"
SHORT_WORDS = 4        # short name: up to 4 words
NAME_WORDS = 20        # full name: up to 20 words
MAX_TRIES = 5          # wrong passwords / answers in a row before the account waits…
LOCK_MINUTES = 15      # …this long


class FormError(ValueError):
    """A mistake in what was typed; shown to the person as a message."""


# ======================================================================
#  Who may do what
# ======================================================================
OPEN = {"admin.login", "admin.login_questions", "admin.setup", "admin.logout", "admin.ping"}
EMPLOYEE = OPEN | {"admin.stock", "admin.product_sell", "admin.product_refill", "admin.stock_return",
                   "admin.giveaways", "admin.giveaway_claim",
                   "admin.account", "admin.account_password", "admin.account_questions"}
OWNER_ONLY = ("admin.employee", "admin.settings")         # endpoints starting with these


def can(endpoint, user=None):
    """May this person open this page or do this action?"""
    user = user or g.get("user")
    if user is None or not endpoint:
        return False
    if user.role == "owner":
        return True
    if endpoint.startswith(OWNER_ONLY):
        return False
    return user.role == "manager" or endpoint in EMPLOYEE


def home_for(user):
    return url_for("admin.dashboard") if can("admin.dashboard", user) else url_for("admin.stock")


# ======================================================================
#  Signing in
# ======================================================================
def _aware(moment):
    """SQLite gives times back without their time zone; they are UTC."""
    return moment.replace(tzinfo=timezone.utc) if moment and moment.tzinfo is None else moment


@bp.before_app_request
def _load_user():
    g.user, g.idle_out = None, False
    uid = session.get("uid")
    if not uid:
        return
    now, seen = time.time(), session.get("seen", 0)
    # the page warns at the limit and signs out itself; the server allows 2 more minutes, because the page
    # tells it about activity (mouse, keys) only every couple of minutes
    if seen and now - seen > current_app.config.get("ADMIN_IDLE_MINUTES", 15) * 60 + 120:
        session.clear()                               # too long without activity: signed out
        g.idle_out = True
        return
    user = db.session.get(User, uid)
    if user and user.is_active:
        g.user = user
        if request.blueprint == "admin":              # only admin pages count as activity
            session["seen"] = now


def login_required(view):
    @wraps(view)
    def wrapped(*args, **kwargs):
        if g.user is None:
            if not User.query.first():
                return redirect(url_for("admin.setup"))
            extra = {"idle": "1"} if g.get("idle_out") else {}
            return redirect(url_for("admin.login", next=request.full_path.rstrip("?"), **extra))
        return view(*args, **kwargs)
    return wrapped


@bp.before_request
def _check_form_token():
    """Every admin form carries a secret token, so another website can't submit forms in your name."""
    if request.method == "POST":
        if request.endpoint == "admin.logout" and g.user is None:
            return                                      # already signed out (e.g. inactivity): nothing to protect
        sent = request.form.get("csrf_token", "")
        if not sent or not secrets.compare_digest(sent, session.get("csrf_token", "")):
            abort(400, "This form expired. Go back, refresh the page and try again.")


@bp.before_request
def _check_access():
    """A page or action the person's role doesn't allow: back to their own start page."""
    if g.user is not None and request.endpoint and not can(request.endpoint):
        if request.endpoint == "admin.dashboard":           # e.g. the website's ADMIN link: just their start page
            return redirect(home_for(g.user))
        flash(f"Your role ({g.user.role_label}) can't do that. Ask the owner if you need it.", "error")
        return redirect(home_for(g.user))


def csrf_token():
    if "csrf_token" not in session:
        session["csrf_token"] = secrets.token_urlsafe(32)
    return session["csrf_token"]


def audit(action, details=""):
    """Record who did what (see AuditLog)."""
    ip = (request.headers.get("X-Forwarded-For", request.remote_addr or "").split(",")[0].strip())[:45]
    db.session.add(AuditLog(user_id=g.user.id if g.get("user") else None, action=action, details=details, ip_address=ip))


def _sign_in(user, how="password"):
    session.clear()
    session.permanent = True
    session["uid"] = user.id
    session["seen"] = time.time()
    user.last_login_at = utcnow()
    user.failed_logins, user.locked_until = 0, None
    g.user = user
    audit("login", f"{user.email} ({how})")
    db.session.commit()


def locked_minutes(user):
    """Minutes left before this account may try again (0 = may try now)."""
    until = _aware(user.locked_until) if user else None
    if until and until > utcnow():
        return max(1, round((until - utcnow()).total_seconds() / 60))
    return 0


def wrong_try(user, what="login.failed"):
    """One more wrong password or answer; after MAX_TRIES the account waits LOCK_MINUTES."""
    user.failed_logins = (user.failed_logins or 0) + 1
    if user.failed_logins >= MAX_TRIES:
        user.failed_logins, user.locked_until = 0, utcnow() + timedelta(minutes=LOCK_MINUTES)
        what = "login.locked"
    audit(what, user.email)
    db.session.commit()


def valid_email(email):
    return bool(re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email))


def new_password(f, field="password", confirm="confirm"):
    password = f.get(field, "")
    if len(password) < 8:
        raise FormError("Choose a password of at least 8 characters.")
    if password != f.get(confirm, ""):
        raise FormError("The two passwords are different.")
    return password


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
            if not name or not valid_email(email):
                raise FormError("Enter your name and a valid email address.")
            user = User(name=name, email=email, role="owner")
            user.set_password(new_password(request.form))
            db.session.add(user)
            db.session.flush()
            _sign_in(user)
            flash(f"Welcome, {user.first_name}. Your admin is ready. Set up your security questions in My account.", "success")
            return redirect(url_for("admin.stock"))
        except FormError as e:
            error = str(e)
    return render_template("admin/setup.html", error=error)


@bp.route("/login", methods=["GET", "POST"])
def login():
    if not User.query.first():
        return redirect(url_for("admin.setup"))
    if g.user:
        return redirect(home_for(g.user))
    error = None
    if request.method == "POST":
        user = User.query.filter_by(email=request.form.get("email", "").strip().lower()).first()
        wait = locked_minutes(user)
        if wait:
            error = f"Too many wrong tries. Wait {wait} minute{'s' if wait > 1 else ''}, then try again."
        elif user and user.is_active and user.check_password(request.form.get("password", "")):
            _sign_in(user)
            target = request.args.get("next", "")
            return redirect(target if target.startswith("/admin") and can_open(target, user) else home_for(user))
        else:
            if user and user.is_active:
                wrong_try(user)
            error = "That email and password don't match."
    return render_template("admin/login.html", error=error, idle=request.args.get("idle") == "1",
                           idle_minutes=current_app.config.get("ADMIN_IDLE_MINUTES", 15),
                           key_missing=not current_app.config.get("SECRET_KEY_SET", True))


def can_open(path, user):
    """Is `path` an admin page this person may open? (for "next" after signing in)"""
    try:
        endpoint = current_app.url_map.bind("").match(path.split("?")[0], method="GET")[0]
    except Exception:
        return False
    return can(endpoint, user)


@bp.route("/logout", methods=["POST"])
def logout():
    idle = request.form.get("idle") == "1"
    if g.user:
        audit("logout.idle" if idle else "logout", g.user.email)
        db.session.commit()
    session.clear()
    return redirect(url_for("admin.login", **({"idle": "1"} if idle else {})))


@bp.route("/ping", methods=["POST"])
def ping():
    """The page is being used (mouse, keys, touch): counts as activity, so you stay signed in."""
    return ("", 204) if g.user else ("", 401)


# ======================================================================
#  Layout: what the top bar and sidebar show on every page
# ======================================================================
@bp.context_processor
def _layout():
    if g.get("user") is None:
        return {"csrf_token": csrf_token, "can": can}
    low = Product.query.filter(Product.stock <= LOW_STOCK).count()
    waiting = Order.query.filter_by(status="waiting").count()
    codes = GiveawayCode.query.filter(GiveawayCode.claimed_at.is_(None)).count()
    return {"low_stock": low, "new_orders": waiting, "codes_waiting": codes, "admin_user": g.user.first_name,
            "admin_role": g.user.role_label, "csrf_token": csrf_token, "can": can, "today": today().isoformat(),
            "idle_minutes": current_app.config.get("ADMIN_IDLE_MINUTES", 15)}


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


# the pages live in their own files; importing them adds their routes to this blueprint
from . import (admin_account, admin_dashboard, admin_employees, admin_giveaways, admin_orders,  # noqa: E402,F401
               admin_photography, admin_settings, admin_stock, admin_upload)
