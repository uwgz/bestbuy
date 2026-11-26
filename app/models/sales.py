"""
Sales recorded by the owner in the admin, and the numbers on the dashboard.

Orders are paid on WhatsApp or in the shop, so a sale only exists here once it is recorded.
Recording a sale takes the units off the product's stock; deleting it puts them back.
"""
from datetime import date, timedelta

from ..db import execute, query
from . import products

CHART_DAYS = 30
LOW_STOCK = 2          # 1–2 units left counts as running low


def record(product_id, qty, unit_cents, sold_on, note="", user_id=None):
    item = products.get(product_id, active_only=False)
    if not item:
        raise ValueError("That product no longer exists.")
    sale_id = execute(
        "INSERT INTO sales (product_id, product_name, category, qty, unit_cents, total_cents, sold_on, note, created_by) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (item["id"], item["name"], item["category"], qty, unit_cents, qty * unit_cents, sold_on, note, user_id))
    # take the units off the stock (never below 0); 0 left = Sold out in the shop
    execute("UPDATE products SET in_stock = CASE WHEN stock_qty > ? THEN 1 ELSE 0 END, "
            "stock_qty = CASE WHEN stock_qty > ? THEN stock_qty - ? ELSE 0 END WHERE id = ?",
            (qty, qty, qty, item["id"]))
    return sale_id


def delete(sale_id):
    """Remove a sale recorded by mistake and put its units back in stock."""
    sale = query("SELECT * FROM sales WHERE id = ?", (sale_id,), one=True)
    if not sale:
        return False
    execute("DELETE FROM sales WHERE id = ?", (sale_id,))
    if sale["product_id"]:
        execute("UPDATE products SET stock_qty = stock_qty + ?, in_stock = 1 WHERE id = ?", (sale["qty"], sale["product_id"]))
    return True


# Stock page filter: key -> (label, days back; None = all time)
PERIODS = {
    "7d": ("Past 7 days", 7, "7 days"),
    "1m": ("Past month", 30, "1 month"),
    "3m": ("Past 3 months", 91, "3 months"),
    "6m": ("Past 6 months", 182, "6 months"),
    "1y": ("Past year", 365, "1 year"),
    "all": ("All time", None, "All time"),
}
DEFAULT_PERIOD = "1m"


def _since(period, today):
    days = PERIODS[period][1]
    return (today - timedelta(days=days - 1)).isoformat() if days else "0000-01-01"


def list_sales(period=DEFAULT_PERIOD, today=None):
    today = today or date.today()
    return [dict(r) for r in query("SELECT * FROM sales WHERE sold_on >= ? AND sold_on <= ? ORDER BY sold_on DESC, id DESC",
                                   (_since(period, today), today.isoformat()))]


def _money(cents):
    return (cents or 0) / 100


def period_summary(period=DEFAULT_PERIOD, today=None):
    """Sales numbers for the Stock page filter."""
    today = today or date.today()
    args = (_since(period, today), today.isoformat())
    t = query("SELECT COUNT(*) AS n, COALESCE(SUM(qty), 0) AS units, COALESCE(SUM(total_cents), 0) AS cents "
              "FROM sales WHERE sold_on >= ? AND sold_on <= ?", args, one=True)
    best = query("SELECT product_name, SUM(qty) AS units FROM sales WHERE sold_on >= ? AND sold_on <= ? "
                 "GROUP BY product_name ORDER BY SUM(qty) DESC, SUM(total_cents) DESC LIMIT 1", args, one=True)
    value = _money(t["cents"])
    return {"label": PERIODS[period][0], "value": value, "units": t["units"], "sales": t["n"],
            "average": value / t["n"] if t["n"] else 0, "best": dict(best) if best else None}


def stock_summary():
    """What is on the shelves right now, valued at today's selling price."""
    units = value = in_stock = sold_out = low = 0
    by_cat = {}
    for p in products.list_products(active_only=False):
        if p["stock_qty"] > 0:
            v = p["stock_qty"] * p["price"]
            units += p["stock_qty"]
            value += v
            in_stock += 1
            low += p["stock_qty"] <= LOW_STOCK
            by_cat[p["category"]] = by_cat.get(p["category"], 0) + v
        else:
            sold_out += 1
    return {"value": value, "units": units, "in_stock": in_stock, "sold_out": sold_out, "low": low, "products": in_stock + sold_out,
            "by_category": sorted(({"key": k, "value": v} for k, v in by_cat.items()), key=lambda r: r["value"], reverse=True)}


def charts(today=None):
    """Dashboard charts: sales per day (last 30 days), sales by category this month, stock value by category."""
    today = today or date.today()
    month_start = today.replace(day=1).isoformat()
    chart_start = (today - timedelta(days=CHART_DAYS - 1)).isoformat()
    per_day = {r["sold_on"]: _money(r["cents"]) for r in query(
        "SELECT sold_on, SUM(total_cents) AS cents FROM sales WHERE sold_on >= ? AND sold_on <= ? GROUP BY sold_on",
        (chart_start, today.isoformat()))}
    days = []
    for k in range(CHART_DAYS):
        d = date.fromisoformat(chart_start) + timedelta(days=k)
        days.append({"date": d.isoformat(), "label": f"{d:%b} {d.day}", "value": per_day.get(d.isoformat(), 0)})
    by_cat = [{"key": r["category"], "value": _money(r["cents"]), "units": r["units"]} for r in query(
        "SELECT category, SUM(total_cents) AS cents, SUM(qty) AS units FROM sales "
        "WHERE sold_on >= ? AND sold_on <= ? GROUP BY category ORDER BY SUM(total_cents) DESC",
        (month_start, today.isoformat()))]
    return {"month_name": f"{today:%B}", "days": days, "by_category": by_cat,
            "stock_by_category": stock_summary()["by_category"]}
