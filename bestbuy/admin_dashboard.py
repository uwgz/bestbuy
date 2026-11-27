"""
Dashboard (/admin/): the shop at a glance, for a chosen period (7 days … all time).
Everything is counted from StockMove (added, refill, sale, return, loss) and from the products themselves.
"""
from collections import defaultdict
from datetime import timedelta
from decimal import Decimal

from flask import render_template, request

from .admin import bp, login_required, today
from .models import Category, Product, StockMove

PERIODS = {   # key: (label on the button, days back; None = everything)
    "7d": ("7 days", 7), "30d": ("30 days", 30), "3m": ("3 months", 91), "1y": ("1 year", 365), "all": ("All time", None),
}
LOW = 2
ZERO = Decimal(0)


def _buckets(period, start, end):
    """Bars for the sales chart: days (7, 30 days), weeks (3 months) or months (a year and more)."""
    if period in ("7d", "30d"):
        days = (end - start).days + 1
        return [(start + timedelta(d), start + timedelta(d), f"{start + timedelta(d):%b} {(start + timedelta(d)).day}") for d in range(days)]
    if period == "3m":
        out, d = [], start
        while d <= end:
            out.append((d, min(d + timedelta(6), end), f"{d:%b} {d.day}"))
            d += timedelta(7)
        return out
    out, d = [], start.replace(day=1)
    while d <= end:
        nxt = (d.replace(day=28) + timedelta(4)).replace(day=1)
        out.append((d, nxt - timedelta(1), f"{d:%b %Y}" if period == "all" else f"{d:%b}"))
        d = nxt
    return out[-24:]


@bp.route("/")
@login_required
def dashboard():
    period = request.args.get("period", "30d")
    period = period if period in PERIODS else "30d"
    end = today()
    days = PERIODS[period][1]
    first = StockMove.query.order_by(StockMove.happened_on).first()
    start = end - timedelta(days - 1) if days else (first.happened_on if first else end)
    moves = StockMove.query.filter(StockMove.happened_on >= start, StockMove.happened_on <= end).all()

    by_kind = defaultdict(list)
    for m in moves:
        by_kind[m.kind].append(m)
    money = lambda kind: sum((Decimal(m.amount) for m in by_kind[kind]), ZERO)
    units = lambda kind: sum(abs(m.qty) for m in by_kind[kind])
    cost_of = lambda kind: sum((Decimal(m.unit_cost) * abs(m.qty) for m in by_kind[kind]), ZERO)

    sales, cogs = money("sale"), cost_of("sale")
    refunds, returned_cost = money("return"), cost_of("return")
    losses = money("loss")
    flow = {
        "sales": sales, "units_sold": units("sale"), "orders": len(by_kind["sale"]),
        "bought": money("added") + money("refill"), "units_bought": units("added") + units("refill"),
        "profit": sales - cogs - losses - refunds + returned_cost,
        "losses": losses, "units_lost": units("loss"), "refunds": refunds, "units_returned": units("return"),
    }
    flow["margin"] = round(flow["profit"] / sales * 100) if sales else 0

    products = Product.query.all()
    now = {
        "units": sum(p.stock for p in products),
        "value_cost": sum((Decimal(p.cost) * p.stock for p in products), ZERO),
        "value_price": sum((p.final_price * p.stock for p in products), ZERO),
        "products": len(products),
        "in_stock": sum(p.stock > 0 for p in products),
        "low": sum(0 < p.stock <= LOW for p in products),
        "sold_out": sum(p.stock == 0 for p in products),
        "on_sale": sum(p.on_sale and p.is_active for p in products),
        "hidden": sum(not p.is_active for p in products),
    }

    bars = []
    for b_start, b_end, label in _buckets(period, start, end):
        value = sum((Decimal(m.amount) for m in by_kind["sale"] if b_start <= m.happened_on <= b_end), ZERO)
        bars.append({"label": label, "value": value})

    top = defaultdict(lambda: {"units": 0, "money": ZERO, "name": ""})
    for m in by_kind["sale"]:
        t = top[m.sku or m.product_name]
        t["units"] += abs(m.qty)
        t["money"] += Decimal(m.amount)
        t["name"] = m.product_name
    top_sellers = sorted(({"sku": k, **v} for k, v in top.items()), key=lambda t: (-t["units"], -t["money"]))[:5]

    by_category = defaultdict(lambda: ZERO)
    category_of = {p.id: p.category for p in products}
    for m in by_kind["sale"]:
        by_category[category_of.get(m.product_id, "")] += Decimal(m.amount)
    categories = Category.as_dict()
    category_sales = sorted(([categories.get(k, ("Other",))[0], v] for k, v in by_category.items() if v), key=lambda r: -r[1])

    running_low = sorted((p for p in products if p.stock <= LOW), key=lambda p: (p.stock, p.short))[:6]
    recent = StockMove.query.order_by(StockMove.created_at.desc(), StockMove.id.desc()).limit(8).all()
    return render_template("admin/dashboard.html", period=period, periods=PERIODS, flow=flow, now=now, bars=bars,
                           top_sellers=top_sellers, category_sales=category_sales, running_low=running_low, recent=recent)
