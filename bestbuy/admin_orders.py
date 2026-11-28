"""
Orders (/admin/orders): every sale made with "Sell" in Stock, newest first.
Search by customer or number, filter Paid / Cancelled, open an order to see its products.
"Cancel sale" (owner and manager) puts the units back on the shelf and records the money given back,
so the dashboard's sales, profit and stock stay right.
"""
from decimal import Decimal

from flask import flash, g, redirect, render_template, request, url_for

from .admin import audit, bp, login_required, today
from .extensions import db
from .models import Order, Product, StockMove, User

PER_PAGE = 30


@bp.route("/orders")
@login_required
def orders():
    status = request.args.get("status", "")
    q = " ".join(request.args.get("q", "").split())[:60]
    page = max(1, request.args.get("page", 1, type=int))
    query = Order.query
    if status in ("paid", "cancelled", "waiting"):
        query = query.filter_by(status=status)
    if q:
        number = q.lstrip("#").lstrip("0")
        match = Order.customer.ilike(f"%{q}%")
        query = query.filter(match | (Order.id == int(number)) if number.isdigit() else match)
    total = query.count()
    rows = query.order_by(Order.sold_on.desc(), Order.id.desc()).offset((page - 1) * PER_PAGE).limit(PER_PAGE).all()
    counts = {s: Order.query.filter_by(status=s).count() for s in ("paid", "cancelled")}
    paid = Order.query.filter_by(status="paid").all() if total < 5000 else []
    sellers = {u.id: u.first_name for u in User.query.all()}
    return render_template("admin/orders.html", rows=rows, status=status, q=q, page=page, total=total, sellers=sellers,
                           pages=max(1, -(-total // PER_PAGE)), counts=counts,
                           takings=sum((o.total for o in paid if o.sold_on == today()), Decimal(0)))


@bp.route("/orders/<int:order_id>/cancel", methods=["POST"])
@login_required
def order_cancel(order_id):
    order = db.session.get(Order, order_id)
    if not order or order.status != "paid":
        flash("Only paid sales can be cancelled.", "error")
        return redirect(url_for("admin.orders"))
    for item in order.items:
        product = db.session.get(Product, item.product_id) if item.product_id else None
        if product:
            product.stock += item.qty
        db.session.add(StockMove(product_id=item.product_id, product_name=item.product_name, sku=item.sku, kind="return",
                                 qty=item.qty, unit_cost=item.unit_cost, amount=item.line_total, happened_on=today(),
                                 reason=f"Sale {order.number} cancelled", order_id=order.id, created_by=g.user.id))
    order.status = "cancelled"
    audit("order.cancel", f"{order.number} ({order.total:,.0f})")
    db.session.commit()
    flash(f"Sale {order.number} cancelled: the units are back in stock.", "success")
    back = request.form.get("_back") or ""
    return redirect(back if back.startswith("/admin") else url_for("admin.orders"))
