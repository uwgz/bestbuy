import re
from datetime import date, timedelta

import pytest

from bestbuy.extensions import db
from bestbuy.models import AuditLog, Order, Product, User


def _token(client, url="/admin/login"):
    html = client.get(url).get_data(as_text=True)
    return re.search(r'name="csrf_token" value="([^"]+)"', html).group(1)


@pytest.fixture
def owner(client):
    """Create the owner on the first-visit page, signed in."""
    t = _token(client, "/admin/setup")
    r = client.post("/admin/setup", data={"csrf_token": t, "name": "Patrick Owner", "email": "Owner@Example.com",
                                          "password": "correct horse", "confirm": "correct horse"})
    assert r.status_code == 302
    client.token = _token(client, "/admin/stock")
    return client


def post(c, url, **data):
    return c.post(url, data={"csrf_token": c.token, **data})


def test_first_visit_creates_owner_then_setup_closes(client, owner):
    assert User.query.count() == 1 and User.query.one().email == "owner@example.com"
    assert client.get("/admin/setup").headers["Location"].endswith("/admin/login")


def test_pages_need_sign_in(client):
    assert client.get("/admin/stock").headers["Location"].endswith("/admin/setup")    # no account yet
    User_ = User(name="A", email="a@b.co"); User_.set_password("12345678")
    db.session.add(User_); db.session.commit()
    assert "/admin/login" in client.get("/admin/stock").headers["Location"]


def test_login_and_logout(client, owner):
    post(owner, "/admin/logout")
    assert "/admin/login" in client.get("/admin/").headers["Location"]
    t = _token(client)
    page = client.post("/admin/login", data={"csrf_token": t, "email": "owner@example.com", "password": "nope"}).get_data(as_text=True)
    assert "don&#39;t match" in page                    # the page writes the apostrophe as &#39;
    r = client.post("/admin/login?next=/admin/stock", data={"csrf_token": t, "email": "OWNER@example.com", "password": "correct horse"})
    assert r.headers["Location"].endswith("/admin/stock")


def test_forms_without_token_are_refused(owner):
    p = Product.query.first()
    assert owner.post(f"/admin/stock/{p.id}/refill", data={"qty": "5"}).status_code == 400


def test_stock_page(owner):
    html = owner.get("/admin/stock").get_data(as_text=True)
    assert html.count('data-dialog="sell"') == 2 * Product.query.count()       # phone and computer layouts
    assert 'id="dlg-sell"' in html and 'id="dlg-refill"' in html and 'id="dlg-product"' in html
    assert "Patrick" in html and "Log out" in html
    html = owner.get("/admin/stock?category=cameras").get_data(as_text=True)
    assert html.count('data-dialog="sell"') == 2 * Product.query.filter_by(category="cameras").count()


def test_sell_records_an_order_and_takes_units_off(owner):
    p = Product.query.filter_by(slug="canon-ef-50mm-f1-8-stm").one()          # 7 in stock
    r = post(owner, f"/admin/stock/{p.id}/sell", qty="2", price="185000", sold_on=date.today().isoformat(), customer="Aline")
    assert r.status_code == 302
    assert db.session.get(Product, p.id).stock == 5
    order = Order.query.one()
    assert order.status == "paid" and order.customer == "Aline" and order.total == 370000
    assert order.items[0].sku == p.sku and order.items[0].product_name == "Canon 50mm f/1.8"
    assert AuditLog.query.filter_by(action="product.sell").count() == 1


def test_cannot_sell_more_than_in_stock_or_in_the_future(owner):
    p = Product.query.filter_by(slug="canon-ef-50mm-f1-8-stm").one()
    post(owner, f"/admin/stock/{p.id}/sell", qty="99", price="1", sold_on=date.today().isoformat())
    assert "Only 7" in owner.get("/admin/stock").get_data(as_text=True)
    tomorrow = (date.today() + timedelta(days=3)).isoformat()
    post(owner, f"/admin/stock/{p.id}/sell", qty="1", price="1", sold_on=tomorrow)
    assert Order.query.count() == 0 and db.session.get(Product, p.id).stock == 7


def test_refill_and_hide(owner):
    p = Product.query.first()
    before = p.stock
    post(owner, f"/admin/stock/{p.id}/refill", qty="4")
    assert db.session.get(Product, p.id).stock == before + 4
    post(owner, f"/admin/stock/{p.id}/visibility")
    assert db.session.get(Product, p.id).is_active is False
    assert owner.get(f"/product/{p.slug}").status_code == 404                  # hidden from the shop


def test_add_and_edit_product(owner):
    form = {"name": "Sony ZV-E10 Vlog Camera with 16-50mm Lens", "short": "", "category": "cameras", "price": "690,000",
            "discount": "0", "stock": "3", "badge": "New", "description": "Made for vloggers.\n- 4K video",
            "photos": "https://images.unsplash.com/photo-1\nhttps://images.unsplash.com/photo-2", "is_active": "1"}
    post(owner, "/admin/stock/add", **form)
    p = Product.query.filter_by(name=form["name"]).one()
    assert p.short == "Sony ZV-E10 Vlog Camera" and p.price == 690000 and len(p.photos) == 2 and p.sku.startswith("CAM-")
    assert owner.get(f"/product/{p.slug}").status_code == 200
    post(owner, f"/admin/stock/{p.id}/edit", **{**form, "short": "ZV-E10", "price": "650000", "discount": "10", "category": "lenses"})
    p = db.session.get(Product, p.id)
    assert p.short == "ZV-E10" and p.final_price == 585000 and p.sku.startswith("LNS-")


def test_add_product_checks_input(owner):
    base = {"category": "audio", "price": "10", "stock": "1"}
    post(owner, "/admin/stock/add", name=" ".join(["word"] * 21), **base)
    assert "20 words or fewer" in owner.get("/admin/stock").get_data(as_text=True)
    post(owner, "/admin/stock/add", name="Thing", short="one two three four five", **base)
    assert "4 words or fewer" in owner.get("/admin/stock").get_data(as_text=True)
    post(owner, "/admin/stock/add", name="Thing", photos="http://not-secure.example/x.jpg", **base)
    assert Product.query.filter_by(name="Thing").count() == 0
