"""
Sales recorded by the owner in the admin, and the numbers on the dashboard.

Orders are paid on WhatsApp or in the shop, so a sale only exists here once it is recorded.
Recording a sale takes the units off the product's stock; deleting it puts them back.
"""
from datetime import date, timedelta

from ..db import execute, query
from . import products

CHART_DAYS = 30


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


def recent(limit=None):
    sql = "SELECT * FROM sales ORDER BY sold_on DESC, id DESC"
    return [dict(r) for r in query(sql + (f" LIMIT {int(limit)}" if limit else ""))]


def _money(cents):
    return (cents or 0) / 100


def summary(today=None):
    """Everything the dashboard shows about money: stock, this month, all time, charts."""
    today = today or date.today()
    month_start = today.replace(day=1).isoformat()
    chart_start = (today - timedelta(days=CHART_DAYS - 1)).isoformat()

    # stock on hand, valued at today's selling price
    stock_units = stock_value = stock_products = 0
    stock_by_cat = {}
    for p in products.list_products(active_only=False):
        if p["stock_qty"] > 0:
            value = p["stock_qty"] * p["price"]
            stock_units += p["stock_qty"]
            stock_products += 1
            stock_value += value
            stock_by_cat[p["category"]] = stock_by_cat.get(p["category"], 0) + value

    month = query("SELECT COUNT(*) AS n, COALESCE(SUM(qty), 0) AS units, COALESCE(SUM(total_cents), 0) AS cents "
                  "FROM sales WHERE sold_on >= ? AND sold_on <= ?", (month_start, today.isoformat()), one=True)
    total = query("SELECT COUNT(*) AS n, COALESCE(SUM(qty), 0) AS units, COALESCE(SUM(total_cents), 0) AS cents FROM sales",
                  one=True)
    best = query("SELECT product_name, SUM(qty) AS units FROM sales WHERE sold_on >= ? AND sold_on <= ? "
                 "GROUP BY product_name ORDER BY SUM(qty) DESC, SUM(total_cents) DESC LIMIT 1",
                 (month_start, today.isoformat()), one=True)

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

    return {
        "month_name": f"{today:%B}",
        "stock": {"value": stock_value, "units": stock_units, "products": stock_products,
                  "by_category": sorted(({"key": k, "value": v} for k, v in stock_by_cat.items()),
                                        key=lambda r: r["value"], reverse=True)},
        "month": {"value": _money(month["cents"]), "units": month["units"], "sales": month["n"],
                  "average": _money(month["cents"]) / month["n"] if month["n"] else 0},
        "total": {"value": _money(total["cents"]), "units": total["units"], "sales": total["n"]},
        "best": dict(best) if best else None,
        "days": days,
        "by_category": by_cat,
    }
