"""Shop: catalogue, product pages, cart and order requests."""
from flask import abort, flash, redirect, render_template, request, session, url_for

from . import bp
from ...helpers import money
from ...models import products, settings


def whatsapp_order_link(lines, total):
    """wa.me link that opens WhatsApp with the order already typed out."""
    if not lines:
        return None
    store = settings.business()["name"]
    text = [f"Hello {store}! I'd like to order:", ""]
    for line in lines:
        p = line["product"]
        text.append(f"• {line['qty']} × {p['name']} — {money(line['subtotal'])}")
        text.append(f"  {url_for('shop.product', slug=p['slug'], _external=True)}")
    text += ["", f"Total: {money(total)}", "", "Is it available? Thank you!"]
    return settings.whatsapp_link("\n".join(text))


@bp.route("/shop")
def shop():
    category = request.args.get("category")
    if category not in products.CATEGORIES:
        category = None
    sort = request.args.get("sort", "")
    q = request.args.get("q", "").strip()
    items = products.list_products(category=category, search=q or None, sort=sort or None)
    return render_template("shop/shop.html", products=items, active=category, q=q, sort=sort)


@bp.route("/product/<slug>")
def product(slug):
    item = products.get_by_slug(slug) or abort(404)
    return render_template("shop/product.html", product=item, related=products.related(item))


def _safe_back(default):
    """Only redirect back to pages on this site."""
    ref = request.referrer or ""
    return ref if ref.startswith(request.host_url) else default


@bp.route("/cart")
def cart():
    lines, total = [], 0.0
    for pid, qty in session.get("cart", {}).items():
        item = products.get(int(pid))
        if item:
            subtotal = item["price"] * qty
            total += subtotal
            lines.append({"product": item, "qty": qty, "subtotal": subtotal})
    return render_template("shop/cart.html", lines=lines, total=total, whatsapp_url=whatsapp_order_link(lines, total))


@bp.route("/cart/add/<int:product_id>", methods=["POST"])
def cart_add(product_id):
    item = products.get(product_id) or abort(404)
    if not item["in_stock"]:
        flash(f"{item['short']} is sold out right now.", "error")
        return redirect(_safe_back(url_for("shop.product", slug=item["slug"])))
    try:
        qty = max(1, min(int(request.form.get("qty", 1) or 1), 99))
    except ValueError:
        qty = 1
    cart = session.get("cart", {})
    cart[str(product_id)] = min(cart.get(str(product_id), 0) + qty, 99)
    session["cart"] = cart
    flash(f"Added {item['short']} to your bag.", "success")
    return redirect(_safe_back(url_for("shop.shop")))


@bp.route("/cart/update/<int:product_id>", methods=["POST"])
def cart_update(product_id):
    cart = session.get("cart", {})
    try:
        qty = int(request.form.get("qty", 0) or 0)
    except ValueError:
        qty = 0
    if qty <= 0:
        cart.pop(str(product_id), None)
    else:
        cart[str(product_id)] = min(qty, 99)
    session["cart"] = cart
    return redirect(url_for("shop.cart"))


@bp.route("/cart/clear", methods=["POST"])
def cart_clear():
    session.pop("cart", None)
    flash("Your bag is empty.", "info")
    return redirect(url_for("shop.cart"))


@bp.route("/checkout", methods=["POST"])
def checkout():
    # Online checkout is switched off for now — orders go through WhatsApp.
    # To take payments online later, connect a payment provider (e.g. Stripe) here.
    flash("Online checkout is coming soon. Please send your order on WhatsApp.", "info")
    return redirect(url_for("shop.cart"))
