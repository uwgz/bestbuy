"""
Admin pages (/admin): sign in, then manage the shop.

Built so far: the layout, the login, and Stock (add, edit, sell, refill, hide / show).
Dashboard, Orders, Giveaways and Settings show their page header until we design them.
"""
import re
import secrets
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from functools import wraps
from zoneinfo import ZoneInfo

from flask import (Blueprint, abort, current_app, flash, g, redirect, render_template, request, session,
                   url_for)

from .extensions import db
from .models import AuditLog, Category, Order, OrderItem, Product, ProductPhoto, User, utcnow

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
    return datetime.now(ZoneInfo(current_app.config.get("TIMEZONE", "Africa/Kigali"))).date()


def _back(default):
    """After a pop-up form: back to the page it was opened from (filters kept)."""
    target = request.form.get("_back", "")
    return target if target.startswith("/admin") else default


def _page(title, subtitle, page_icon, button=None):
    return render_template("admin/page.html", title=title, subtitle=subtitle, page_icon=page_icon, button=button)


@bp.route("/")
@login_required
def dashboard():
    return _page("Dashboard", "Your store at a glance.", "layout")


@bp.route("/orders")
@login_required
def orders():
    return _page("Orders", "Sales made in the shop and orders sent from the website.", "receipt")


@bp.route("/giveaways")
@login_required
def giveaways():
    return _page("Giveaways", "A random visitor wins a prize; check their code here.", "gift", button="Start a giveaway")


@bp.route("/settings")
@login_required
def settings():
    return _page("Settings", "Store details, WhatsApp number, and your account.", "settings")


# ======================================================================
#  Stock
# ======================================================================
@bp.route("/stock")
@login_required
def stock():
    everything = Product.query.order_by(Product.position, Product.id).all()
    categories = Category.as_dict()
    cat = request.args.get("category", "")
    cat = cat if cat in categories else ""
    items = [p for p in everything if p.category == cat] if cat else everything
    counts = {key: sum(p.category == key for p in everything) for key in categories}
    return render_template("admin/stock.html", items=items, total=len(everything), counts=counts, cat=cat)


def _product_or_404(product_id):
    return db.session.get(Product, product_id) or abort(404)


def _whole(value, label, low=0, high=100000):
    try:
        number = int(str(value).strip())
    except ValueError:
        raise FormError(f"{label}: enter a whole number.")
    if not low <= number <= high:
        raise FormError(f"{label}: between {low} and {high:,}.")
    return number


def _money(value, label):
    text = str(value or "").replace(",", "").replace(" ", "").strip()
    try:
        amount = Decimal(text).quantize(Decimal("0.01"))
    except InvalidOperation:
        raise FormError(f"{label}: enter an amount, like 1290000.")
    if amount < 0 or amount > Decimal("9999999999"):
        raise FormError(f"{label}: enter an amount, like 1290000.")
    return amount


def _words(text):
    return [w for w in text.split() if w.strip("-–—|/")]


def _slug(name, exclude_id=None):
    base = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")[:120] or "product"
    slug, n = base, 2
    while True:
        clash = Product.query.filter(Product.slug == slug)
        if exclude_id:
            clash = clash.filter(Product.id != exclude_id)
        if not clash.first():
            return slug
        slug, n = f"{base}-{n}", n + 1


def _product_from_form(f, product=None):
    """Read the Add / Edit form; raises FormError with a clear message when something is wrong."""
    name = " ".join(f.get("name", "").split())
    if not name:
        raise FormError("Give the product a name.")
    if len(_words(name)) > NAME_WORDS or len(name) > 200:
        raise FormError(f"Keep the product name to {NAME_WORDS} words or fewer.")
    short = " ".join(f.get("short", "").split()) or " ".join(_words(name)[:SHORT_WORDS])
    if len(_words(short)) > SHORT_WORDS or len(short) > 40:
        raise FormError(f"Keep the short name to {SHORT_WORDS} words or fewer.")
    category = f.get("category", "")
    if category not in Category.as_dict():
        raise FormError("Choose a category.")
    photos = [line.strip() for line in f.get("photos", "").splitlines() if line.strip()]
    for url in photos:
        if not (url.startswith("https://") or url.startswith("/static/")):
            raise FormError("Photo links must start with https:// (one link per line).")
    return {
        "name": name, "short": short, "category": category,
        "price": _money(f.get("price"), "Price"),
        "discount": _whole(f.get("discount") or 0, "Discount", 0, 90),
        "badge": " ".join(f.get("badge", "").split())[:32],
        "stock": _whole(f.get("stock") or 0, "Units in stock"),
        "description": f.get("description", "").strip(),
        "is_active": bool(f.get("is_active")),
        "photos": photos,
    }


def _apply(product, data):
    photos = data.pop("photos")
    for key, value in data.items():
        setattr(product, key, value)
    product.category_info = db.session.get(Category, data["category"])      # its SKU code comes from here
    if [p.url for p in product.photo_rows] != photos:
        product.photo_rows = [ProductPhoto(url=url, position=k) for k, url in enumerate(photos)]


@bp.route("/stock/add", methods=["POST"])
@login_required
def product_add():
    try:
        data = _product_from_form(request.form)
        product = Product(slug=_slug(data["name"]),
                          position=(db.session.query(db.func.max(Product.position)).scalar() or 0) + 1)
        _apply(product, data)
        db.session.add(product)
        db.session.flush()
        audit("product.add", f"{product.sku} {product.short}")
        db.session.commit()
        flash(f"{product.short} added ({product.sku}).", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(_back(url_for("admin.stock")))


@bp.route("/stock/<int:product_id>/edit", methods=["POST"])
@login_required
def product_edit(product_id):
    product = _product_or_404(product_id)
    try:
        data = _product_from_form(request.form, product)
        if data["name"] != product.name:
            product.slug = _slug(data["name"], exclude_id=product.id)     # the shop address follows the name
        _apply(product, data)
        audit("product.edit", f"{product.sku} {product.short}")
        db.session.commit()
        flash(f"{product.short} saved.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(_back(url_for("admin.stock")))


@bp.route("/stock/<int:product_id>/sell", methods=["POST"])
@login_required
def product_sell(product_id):
    """Record a sale made in the shop: an order (paid), and the units come off the stock."""
    product = _product_or_404(product_id)
    f = request.form
    try:
        qty = _whole(f.get("qty"), "How many", 1, 10000)
        if qty > product.stock:
            raise FormError(f"Only {product.stock} {product.short} in stock. Refill it first."
                            if product.stock else f"{product.short} is sold out. Refill it first.")
        price = _money(f.get("price"), "Price each")
        try:
            sold_on = date.fromisoformat(f.get("sold_on", ""))
        except ValueError:
            raise FormError("Choose the date of the sale.")
        if sold_on > today():
            raise FormError("The sale date can't be in the future.")
        order = Order(status="paid", source="shop", sold_on=sold_on, customer=" ".join(f.get("customer", "").split())[:120],
                      note=f.get("note", "").strip()[:300], created_by=g.user.id)
        order.items = [OrderItem(product_id=product.id, product_name=product.short, sku=product.sku, qty=qty, unit_price=price)]
        product.stock -= qty
        db.session.add(order)
        db.session.flush()
        audit("product.sell", f"{order.number}: {qty} × {product.sku} at {price}")
        db.session.commit()
        flash(f"Sold {qty} × {product.short}. {product.stock} left.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(_back(url_for("admin.stock")))


@bp.route("/stock/<int:product_id>/refill", methods=["POST"])
@login_required
def product_refill(product_id):
    """New units of the same product arrived."""
    product = _product_or_404(product_id)
    try:
        qty = _whole(request.form.get("qty"), "How many arrived", 1, 100000)
        product.stock += qty
        audit("product.refill", f"+{qty} × {product.sku}")
        db.session.commit()
        flash(f"Added {qty} × {product.short}. {product.stock} in stock now.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(_back(url_for("admin.stock")))


@bp.route("/stock/<int:product_id>/visibility", methods=["POST"])
@login_required
def product_visibility(product_id):
    product = _product_or_404(product_id)
    product.is_active = not product.is_active
    audit("product.show" if product.is_active else "product.hide", product.sku)
    db.session.commit()
    flash(f"{product.short} is {'back in' if product.is_active else 'hidden from'} the shop.", "success")
    return redirect(_back(url_for("admin.stock")))
