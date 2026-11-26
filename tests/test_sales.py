from datetime import date, timedelta

from app.db import execute, query


def _product(app, qty=5, price_cents=200000, discount=0):
    with app.app_context():
        return execute("INSERT INTO products (slug, name, category, price_cents, discount_percent, stock_qty, in_stock) "
                       "VALUES ('cam-x', 'Camera X', 'cameras', ?, ?, ?, ?)", (price_cents, discount, qty, 1 if qty else 0))


def _stock(app, pid):
    with app.app_context():
        r = query("SELECT stock_qty, in_stock FROM products WHERE id = ?", (pid,), one=True)
        return r["stock_qty"], r["in_stock"]


def _sell(owner, pid, qty="2", price="1500", day=None):
    return owner.post("/altar/sales", data={"product_id": str(pid), "qty": qty, "unit_price": price,
                                            "sold_on": day or date.today().isoformat(), "note": "MoMo"})


def test_recording_a_sale_takes_units_off_stock(owner, app):
    pid = _product(app, qty=3)
    assert _sell(owner, pid, qty="2").status_code == 302
    assert _stock(app, pid) == (1, 1)
    _sell(owner, pid, qty="1")
    assert _stock(app, pid) == (0, 0)                      # last unit sold -> Sold out in the shop
    with app.app_context():
        rows = query("SELECT qty, unit_cents, total_cents, product_name, category FROM sales ORDER BY id")
    assert [tuple(r) for r in rows] == [(2, 150000, 300000, "Camera X", "cameras"), (1, 150000, 150000, "Camera X", "cameras")]


def test_removing_a_sale_puts_units_back(owner, app):
    pid = _product(app, qty=1)
    _sell(owner, pid, qty="1")
    with app.app_context():
        sale_id = query("SELECT id FROM sales", one=True)["id"]
    owner.post(f"/altar/sales/{sale_id}/delete")
    assert _stock(app, pid) == (1, 1)
    with app.app_context():
        assert query("SELECT COUNT(*) AS n FROM sales", one=True)["n"] == 0


def test_sale_form_checks_input(owner, app):
    pid = _product(app)
    for data, msg in [({"product_id": ""}, "Choose the product"), ({"qty": "0"}, "Quantity must be between"),
                      ({"unit_price": ""}, "Enter a price"), ({"sold_on": (date.today() + timedelta(days=5)).isoformat()}, "future")]:
        form = {"product_id": str(pid), "qty": "1", "unit_price": "10", "sold_on": date.today().isoformat(), **data}
        r = owner.post("/altar/sales", data=form, follow_redirects=True)
        assert msg in r.get_data(as_text=True)
    with app.app_context():
        assert query("SELECT COUNT(*) AS n FROM sales", one=True)["n"] == 0


def test_dashboard_has_charts_but_no_money_cards_or_buttons(owner, app):
    pid = _product(app, qty=4, price_cents=100000)
    _sell(owner, pid, qty="1", price="900")
    html = owner.get("/altar/").get_data(as_text=True)
    assert "Sales, last 30 days" in html and 'class="cbar' in html and "Sales by category" in html
    assert "Stock value</span>" not in html and "Recent sales" not in html     # those live on the Stock page
    assert "Quick actions" not in html and '<a class="stat"' not in html and "data-modal=" not in html
    from app.models import sales
    with app.app_context():
        c = sales.charts()
    assert len(c["days"]) == 30 and c["days"][-1]["value"] == 900


def test_stock_page_has_stock_sales_filter_and_history(owner, app):
    pid = _product(app, qty=4, price_cents=100000)
    _sell(owner, pid, qty="1", price="900")
    _sell(owner, pid, qty="2", price="800", day=(date.today() - timedelta(days=60)).isoformat())
    html = owner.get("/altar/products").get_data(as_text=True)          # default: past month
    assert "In stock now" in html and "Stock value" in html and "Sold out" in html
    for short in ("7 days", "1 month", "3 months", "6 months", "1 year", "All time"):
        assert short in html
    assert "Sales · past month" in html and html.count('class="list-row sale-row"') == 1
    html = owner.get("/altar/products?period=3m").get_data(as_text=True)
    assert html.count('class="list-row sale-row"') == 2 and "Sales · past 3 months" in html
    assert owner.get("/altar/products?period=nonsense").status_code == 200
    assert owner.get("/altar/sales").headers["Location"].endswith("/altar/products#sales")
    from app.models import sales
    with app.app_context():
        assert sales.period_summary("7d")["value"] == 900 and sales.period_summary("all")["units"] == 3
        assert sales.period_summary("all")["average"] == 1250
        st = sales.stock_summary()
    assert st["units"] >= 1 and st["products"] >= 1


def test_product_form_sets_units(owner, app):
    r = owner.post("/altar/products/new", data={"name": "Lens Y", "category": "lenses", "price": "500", "stock_qty": "0",
                                                "is_active": "1", "discount_percent": "0"})
    assert r.status_code == 302
    with app.app_context():
        row = query("SELECT stock_qty, in_stock FROM products WHERE name = 'Lens Y'", one=True)
    assert (row["stock_qty"], row["in_stock"]) == (0, 0)


def test_old_database_gets_stock_column(tmp_path, backend, request):
    """A database made before units existed gets the column, with in-stock products set to 1 unit."""
    from conftest import make_app
    from app import db
    app = make_app(tmp_path, backend, request)
    with app.app_context():
        execute("ALTER TABLE products DROP COLUMN stock_qty")
        execute("INSERT INTO products (slug, name, category, price_cents, in_stock) VALUES ('a', 'A', 'audio', 100, 1)")
        execute("INSERT INTO products (slug, name, category, price_cents, in_stock) VALUES ('b', 'B', 'audio', 100, 0)")
        db.init_schema()
        rows = query("SELECT slug, stock_qty FROM products ORDER BY slug")
    assert [(r["slug"], r["stock_qty"]) for r in rows] == [("a", 1), ("b", 0)]


def test_products_list_has_sell_button(owner, app):
    pid = _product(app, qty=2, price_cents=150000)
    html = owner.get("/altar/products").get_data(as_text=True)
    assert f'data-sale-id="{pid}"' in html and 'data-sale-stock="2"' in html and 'id="sell-one"' in html
    assert "2 in stock" in html
    r = owner.post("/altar/sales", data={"product_id": str(pid), "qty": "1", "unit_price": "1400", "sold_on": date.today().isoformat(),
                                         "_back": "/altar/products"})
    assert r.headers["Location"].endswith("/altar/products")
    assert _stock(app, pid) == (1, 1)
    assert 'data-label="Sales"' not in owner.get("/altar/").get_data(as_text=True)     # no separate Sales page
