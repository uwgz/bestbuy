import re
from datetime import date, timedelta

import pytest

from bestbuy.extensions import db
from bestbuy.admin import today
from bestbuy.models import AuditLog, Order, Product, Setting, StockMove, User


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
    for dialog in ("sell", "refill", "media", "product", "return"):
        assert f'id="dlg-{dialog}"' in html
    assert "Patrick" in html and "Log out" in html
    html = owner.get("/admin/stock?category=cameras").get_data(as_text=True)
    assert html.count('data-dialog="sell"') == 2 * Product.query.filter_by(category="cameras").count()


def sell(c, p, **extra):
    form = {"qty": "2", "price": "185000", "day": today().isoformat(), "customer": "Aline", **extra}
    return post(c, f"/admin/stock/{p.id}/sell", **form)


def test_sell_records_an_order_and_takes_units_off(owner):
    p = Product.query.filter_by(slug="canon-ef-50mm-f1-8-stm").one()          # 7 in stock
    assert sell(owner, p).status_code == 302
    assert db.session.get(Product, p.id).stock == 5
    order = Order.query.one()
    assert order.status == "paid" and order.customer == "Aline" and order.total == 370000
    assert order.items[0].sku == p.sku and order.items[0].product_name == "Canon 50mm f/1.8"
    assert order.items[0].unit_cost == p.cost
    move = StockMove.query.filter_by(kind="sale").one()
    assert move.qty == -2 and move.amount == 370000 and move.order_id == order.id
    assert AuditLog.query.filter_by(action="product.sell").count() == 1


def test_sell_checks_every_field(owner):
    p = Product.query.filter_by(slug="canon-ef-50mm-f1-8-stm").one()
    sell(owner, p, qty="99")
    assert "Only 7" in owner.get("/admin/stock").get_data(as_text=True)
    sell(owner, p, day=(today() + timedelta(days=3)).isoformat())           # the future
    sell(owner, p, customer="")                                               # customer is required
    sell(owner, p, day="")
    assert Order.query.count() == 0 and db.session.get(Product, p.id).stock == 7


def test_refill_averages_the_buying_price(owner):
    p = Product.query.filter_by(slug="canon-ef-50mm-f1-8-stm").one()
    p.cost = 100000; db.session.commit()                                       # 7 units at 100,000
    post(owner, f"/admin/stock/{p.id}/refill", qty="3", cost="200000", day=today().isoformat())
    p = db.session.get(Product, p.id)
    assert p.stock == 10 and p.cost == 130000                                  # (7×100k + 3×200k) / 10
    move = StockMove.query.filter_by(kind="refill").one()
    assert move.qty == 3 and move.amount == 600000
    post(owner, f"/admin/stock/{p.id}/refill", qty="3", day=today().isoformat())   # no buying price: refused
    assert db.session.get(Product, p.id).stock == 10


def test_hide_and_show(owner):
    p = Product.query.first()
    post(owner, f"/admin/stock/{p.id}/visibility")
    assert db.session.get(Product, p.id).is_active is False
    assert owner.get(f"/product/{p.slug}").status_code == 404                  # hidden from the shop
    post(owner, f"/admin/stock/{p.id}/visibility")
    assert owner.get(f"/product/{p.slug}").status_code == 200


PRODUCT = {"name": "Sony ZV-E10 Vlog Camera with 16-50mm Lens", "short": "Sony ZV-E10", "category": "cameras",
           "price": "690,000", "cost": "560000", "stock": "3", "description": "Made for vloggers.\n- 4K video"}


def test_add_edit_and_photos(owner):
    post(owner, "/admin/stock/add", **PRODUCT)
    p = Product.query.filter_by(name=PRODUCT["name"]).one()
    assert p.short == "Sony ZV-E10" and p.price == 690000 and p.cost == 560000 and p.stock == 3 and p.sku.startswith("CAM-")
    move = StockMove.query.filter_by(kind="added", product_id=p.id).one()
    assert move.qty == 3 and move.amount == 1680000
    assert owner.get(f"/product/{p.slug}").status_code == 200

    post(owner, f"/admin/stock/{p.id}/edit", **{**PRODUCT, "short": "ZV-E10", "price": "650000", "category": "lenses", "stock": "99"})
    p = db.session.get(Product, p.id)
    assert p.short == "ZV-E10" and p.price == 650000 and p.sku.startswith("LNS-") and p.stock == 3   # edit never changes units

    post(owner, f"/admin/stock/{p.id}/media", photos="https://images.unsplash.com/photo-1\nhttps://images.unsplash.com/photo-2",
         discount="10", badge="New")
    p = db.session.get(Product, p.id)
    assert len(p.photos) == 2 and p.final_price == 585000 and p.badge == "New"
    post(owner, f"/admin/stock/{p.id}/media", photos="", discount="0", badge="")       # photos and discount may be empty
    p = db.session.get(Product, p.id)
    assert p.photos == [] and not p.on_sale and p.badge == ""
    post(owner, f"/admin/stock/{p.id}/media", photos="http://not-secure.example/x.jpg", discount="0")
    assert "https://" in owner.get("/admin/stock").get_data(as_text=True)


def test_add_product_needs_every_field(owner):
    for missing in ("name", "short", "category", "price", "cost", "stock", "description"):
        post(owner, "/admin/stock/add", **{**PRODUCT, missing: ""})
    post(owner, "/admin/stock/add", **{**PRODUCT, "name": " ".join(["word"] * 21)})
    assert "20 words or fewer" in owner.get("/admin/stock").get_data(as_text=True)
    post(owner, "/admin/stock/add", **{**PRODUCT, "short": "one two three four five"})
    assert "4 words or fewer" in owner.get("/admin/stock").get_data(as_text=True)
    assert Product.query.filter_by(category="cameras").filter(Product.name.like("Sony ZV%")).count() == 0 \
        and Product.query.filter(Product.name.like("word%")).count() == 0


def test_return_and_loss(owner):
    p = Product.query.filter_by(slug="canon-ef-50mm-f1-8-stm").one()          # 7 in stock
    base = {"product_id": str(p.id), "qty": "1", "day": today().isoformat(), "reason": "Wrong lens mount"}
    post(owner, "/admin/stock/return", kind="return", refund="185000", **base)
    assert db.session.get(Product, p.id).stock == 8
    post(owner, "/admin/stock/return", kind="loss", **{**base, "qty": "2", "reason": "Dropped"})
    assert db.session.get(Product, p.id).stock == 6
    post(owner, "/admin/stock/return", kind="loss", **{**base, "reason": ""})          # reason required
    post(owner, "/admin/stock/return", kind="loss", **{**base, "qty": "50"})           # more than in stock
    assert db.session.get(Product, p.id).stock == 6
    assert StockMove.query.filter_by(kind="return").one().amount == 185000
    loss = StockMove.query.filter_by(kind="loss").one()
    assert loss.qty == -2 and loss.amount == p.cost * 2


def test_dashboard_counts_the_moves(owner):
    p = Product.query.filter_by(slug="canon-ef-50mm-f1-8-stm").one()
    sell(owner, p)
    html = owner.get("/admin/").get_data(as_text=True)
    assert "Hello, Patrick" in html and "In stock now" in html and "Canon 50mm f/1.8" in html
    assert "RWF 370,000" in html                                               # sales in the period
    for period in ("7d", "30d", "3m", "1y", "all", "nonsense"):
        assert owner.get(f"/admin/?period={period}").status_code == 200


def test_settings(owner):
    assert owner.get("/admin/settings").status_code == 200
    post(owner, "/admin/settings/contact", phone="+250 788 123 456", whatsapp="+250 788 123 456", email="Hi@Shop.rw")
    post(owner, "/admin/settings/hours", hours_week_open="08:00", hours_week_close="19:00",
         hours_sat_open="09:00", hours_sat_close="17:00", hours_sun_closed="1")
    post(owner, "/admin/settings/social", instagram="https://instagram.com/bestbuy250", facebook="", tiktok="")
    values = {s.key: s.value for s in Setting.query.all()}
    assert values["whatsapp"] == "250788123456" and values["email"] == "hi@shop.rw"
    assert values["hours_week"] == "08:00-19:00" and values["hours_sun"] == ""
    assert values["instagram"].endswith("bestbuy250")
    assert "Mon–Fri 08:00–19:00" in owner.get("/contact").get_data(as_text=True)
    post(owner, "/admin/settings/hours", hours_week_open="19:00", hours_week_close="08:00", hours_sat_closed="1", hours_sun_closed="1")
    assert db.session.get(Setting, "hours_week").value == "08:00-19:00"        # closing before opening: refused
    post(owner, "/admin/settings/contact", phone="", whatsapp="250788123456", email="hi@shop.rw")
    assert db.session.get(Setting, "phone").value == "+250 788 123 456"        # phone required
