"""
Stock (/admin/stock): products and every change to their units.

    + Add product     a new product with the units you bought and what each cost you
    Return / loss     a customer brought something back, or units were damaged / lost
    Sell              a sale in the shop (an order, paid)
    Refill            more units of the same product bought
    Photos & discount pictures, discount % and its label (filled in later)
    Edit              name, category, prices, description
    Hide / show       take it off the shop or put it back
Each change to units is written to StockMove, which the dashboard counts.
"""
import re
from datetime import date
from decimal import Decimal

from flask import abort, flash, g, redirect, render_template, request, url_for

from .admin import FormError, _back, amount, audit, bp, login_required, text, today, whole
from .extensions import db
from .models import Category, Order, OrderItem, Product, ProductPhoto, StockMove

SHORT_WORDS = 4        # short name: up to 4 words
NAME_WORDS = 20        # full name: up to 20 words


@bp.route("/stock")
@login_required
def stock():
    everything = Product.query.order_by(Product.position, Product.id).all()
    categories = Category.as_dict()
    cat = request.args.get("category", "")
    cat = cat if cat in categories else ""
    items = [p for p in everything if p.category == cat] if cat else everything
    counts = {key: sum(p.category == key for p in everything) for key in categories}
    return render_template("admin/stock.html", items=items, total=len(everything), counts=counts, cat=cat,
                           all_products=everything)


# ---------------------------------------------------------------- helpers
def _product_or_404(product_id):
    return db.session.get(Product, product_id) or abort(404)


def _words(value):
    return [w for w in value.split() if w.strip("-–—|/")]


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


def _day(f, name="day"):
    try:
        day = date.fromisoformat(f.get(name, ""))
    except ValueError:
        raise FormError("Choose the date.")
    if day > today():
        raise FormError("The date can't be in the future.")
    return day


def _move(product, kind, qty, unit_cost, money, day, reason="", order=None):
    db.session.add(StockMove(product_id=product.id, product_name=product.short, sku=product.sku, kind=kind, qty=qty,
                             unit_cost=unit_cost, amount=money, reason=reason, happened_on=day,
                             order_id=order.id if order else None, created_by=g.user.id))


def _details(f):
    """Name, short name, category, prices and description: all required."""
    name = text(f, "name", "the product name", limit=200)
    if len(_words(name)) > NAME_WORDS:
        raise FormError(f"Keep the product name to {NAME_WORDS} words or fewer.")
    short = text(f, "short", "the short name", limit=40)
    if len(_words(short)) > SHORT_WORDS:
        raise FormError(f"Keep the short name to {SHORT_WORDS} words or fewer.")
    category = f.get("category", "")
    if category not in Category.as_dict():
        raise FormError("Choose a category.")
    description = (f.get("description") or "").strip()
    if not description:
        raise FormError("Write a short description.")
    return {"name": name, "short": short, "category": category, "price": amount(f.get("price"), "Selling price"),
            "cost": amount(f.get("cost"), "Buying price"), "description": description}


def _done(message):
    db.session.commit()
    flash(message, "success")
    return redirect(_back(url_for("admin.stock")))


def _failed(error):
    db.session.rollback()
    flash(str(error), "error")
    return redirect(_back(url_for("admin.stock")))


# ---------------------------------------------------------------- actions
@bp.route("/stock/add", methods=["POST"])
@login_required
def product_add():
    try:
        data = _details(request.form)
        units = whole(request.form.get("stock"), "Units bought", 1, 100000)
        product = Product(slug=_slug(data["name"]), stock=units, is_active=True,
                          position=(db.session.query(db.func.max(Product.position)).scalar() or 0) + 1, **data)
        product.category_info = db.session.get(Category, data["category"])
        db.session.add(product)
        db.session.flush()
        _move(product, "added", units, product.cost, product.cost * units, today(), "New product")
        audit("product.add", f"{product.sku} {product.short}: {units} units at {product.cost}")
        return _done(f"{product.short} added ({product.sku}). Add its photos with “Photos & discount”.")
    except FormError as e:
        return _failed(e)


@bp.route("/stock/<int:product_id>/edit", methods=["POST"])
@login_required
def product_edit(product_id):
    product = _product_or_404(product_id)
    try:
        data = _details(request.form)
        if data["name"] != product.name:
            product.slug = _slug(data["name"], exclude_id=product.id)       # the shop address follows the name
        for key, value in data.items():
            setattr(product, key, value)
        product.category_info = db.session.get(Category, data["category"])
        audit("product.edit", f"{product.sku} {product.short}")
        return _done(f"{product.short} saved.")
    except FormError as e:
        return _failed(e)


@bp.route("/stock/<int:product_id>/media", methods=["POST"])
@login_required
def product_media(product_id):
    """Photos, discount and its label: filled in later, so they may be empty."""
    product = _product_or_404(product_id)
    f = request.form
    try:
        photos = [line.strip() for line in (f.get("photos") or "").splitlines() if line.strip()]
        for url in photos:
            if not (url.startswith("https://") or url.startswith("/static/")):
                raise FormError("Photo links must start with https:// (one link per line).")
        product.discount = whole(f.get("discount") or 0, "Discount", 0, 90)
        product.badge = text(f, "badge", "the label", required=False, limit=32)
        if [p.url for p in product.photo_rows] != photos:
            product.photo_rows = [ProductPhoto(url=url, position=k) for k, url in enumerate(photos)]
        audit("product.media", f"{product.sku}: {len(photos)} photos, {product.discount}% off")
        return _done(f"{product.short}: photos and discount saved.")
    except FormError as e:
        return _failed(e)


@bp.route("/stock/<int:product_id>/sell", methods=["POST"])
@login_required
def product_sell(product_id):
    """A sale in the shop: an order (paid); the units come off the stock."""
    product = _product_or_404(product_id)
    f = request.form
    try:
        qty = whole(f.get("qty"), "How many", 1, 10000)
        if qty > product.stock:
            raise FormError(f"Only {product.stock} {product.short} in stock. Refill it first."
                            if product.stock else f"{product.short} is sold out. Refill it first.")
        price = amount(f.get("price"), "Price each")
        day = _day(f)
        customer = text(f, "customer", "the customer's name or phone", limit=120)
        order = Order(status="paid", source="shop", sold_on=day, customer=customer, created_by=g.user.id)
        order.items = [OrderItem(product_id=product.id, product_name=product.short, sku=product.sku, qty=qty,
                                 unit_price=price, unit_cost=product.cost)]
        db.session.add(order)
        db.session.flush()
        product.stock -= qty
        _move(product, "sale", -qty, product.cost, price * qty, day, f"Sold to {customer}", order)
        audit("product.sell", f"{order.number}: {qty} × {product.sku} at {price}")
        return _done(f"Sold {qty} × {product.short}. {product.stock} left.")
    except FormError as e:
        return _failed(e)


@bp.route("/stock/<int:product_id>/refill", methods=["POST"])
@login_required
def product_refill(product_id):
    """More units bought. The buying price becomes the average of old and new units."""
    product = _product_or_404(product_id)
    f = request.form
    try:
        qty = whole(f.get("qty"), "How many arrived", 1, 100000)
        unit_cost = amount(f.get("cost"), "Buying price each")
        day = _day(f)
        old_units = max(product.stock, 0)
        product.cost = ((Decimal(product.cost) * old_units + unit_cost * qty) / (old_units + qty)).quantize(Decimal("0.01"))
        product.stock += qty
        _move(product, "refill", qty, unit_cost, unit_cost * qty, day, "Refill")
        audit("product.refill", f"+{qty} × {product.sku} at {unit_cost}")
        return _done(f"Added {qty} × {product.short}. {product.stock} in stock now.")
    except FormError as e:
        return _failed(e)


@bp.route("/stock/return", methods=["POST"])
@login_required
def stock_return():
    """A customer brought units back (back on the shelf, money given back), or units were damaged / lost."""
    f = request.form
    try:
        try:
            product = db.session.get(Product, int(f.get("product_id") or 0))
        except ValueError:
            product = None
        if not product:
            raise FormError("Choose the product.")
        kind = f.get("kind")
        if kind not in ("return", "loss"):
            raise FormError("Choose what happened: returned by a customer, or damaged / lost.")
        qty = whole(f.get("qty"), "How many", 1, 100000)
        day = _day(f)
        reason = text(f, "reason", "the reason")
        if kind == "return":
            refund = amount(f.get("refund"), "Money given back", allow_zero=True)
            product.stock += qty
            _move(product, "return", qty, product.cost, refund, day, reason)
            audit("stock.return", f"+{qty} × {product.sku}, refund {refund}: {reason}")
            return _done(f"Return saved: {qty} × {product.short} back in stock.")
        if qty > product.stock:
            raise FormError(f"Only {product.stock} {product.short} in stock.")
        product.stock -= qty
        _move(product, "loss", -qty, product.cost, Decimal(product.cost) * qty, day, reason)
        audit("stock.loss", f"-{qty} × {product.sku}: {reason}")
        return _done(f"Loss saved: {qty} × {product.short} written off.")
    except FormError as e:
        return _failed(e)


@bp.route("/stock/<int:product_id>/visibility", methods=["POST"])
@login_required
def product_visibility(product_id):
    product = _product_or_404(product_id)
    product.is_active = not product.is_active
    audit("product.show" if product.is_active else "product.hide", product.sku)
    return _done(f"{product.short} is {'back in' if product.is_active else 'hidden from'} the shop.")
