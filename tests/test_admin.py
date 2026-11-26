from datetime import date, timedelta
from pathlib import Path

from conftest import PASSWORD, photo_bytes


# ---------- access ----------
def test_admin_requires_login(client, owner):
    owner.post("/altar/logout")
    r = client.get("/altar/products")
    assert r.status_code == 302 and "/altar/login" in r.headers["Location"]


def test_setup_only_once(owner):
    assert owner.get("/altar/setup").headers["Location"].endswith("/altar/login")


def test_setup_rejects_short_password(client):
    r = client.post("/altar/setup", data={"name": "A", "email": "a@b.co", "password": "short", "confirm": "short"})
    assert b"at least 10 characters" in r.data


def test_login_and_wrong_password(owner):
    owner.post("/altar/logout")
    assert owner.post("/altar/login", data={"email": "owner@example.com", "password": "nope"}).status_code == 401
    r = owner.post("/altar/login", data={"email": "owner@example.com", "password": PASSWORD})
    assert r.headers["Location"].endswith("/altar/")


def test_login_throttled(owner):
    owner.post("/altar/logout")
    for _ in range(5):
        owner.post("/altar/login", data={"email": "owner@example.com", "password": "nope"})
    r = owner.post("/altar/login", data={"email": "owner@example.com", "password": PASSWORD})
    assert r.status_code == 429


def test_login_ignores_external_next(owner):
    owner.post("/altar/logout")
    r = owner.post("/altar/login?next=//evil.example.com", data={"email": "owner@example.com", "password": PASSWORD})
    assert r.headers["Location"] == "/altar/"


def test_csrf_blocks_forged_post(app, owner):
    app.config["CSRF_ENABLED"] = True
    assert owner.post("/altar/settings", data={"phone": "000"}).status_code == 400


# ---------- products ----------
def _pid(client, response):
    import re
    html = client.get(response.headers["Location"]).get_data(as_text=True)
    return int(re.search(r"/altar/products/(\d+)/delete", html).group(1))


def _slug(response):
    return response.headers["Location"].rstrip("/").split("/")[-1]


def _new_product(client, **extra):
    data = {"name": "Test Camera", "category": "cameras", "price": "1,000.00", "discount_percent": "0",
            "is_active": "1", "stock_qty": "3", "description": "A camera", **extra}
    return client.post("/altar/products/new", data=data, content_type="multipart/form-data")


def test_create_product_with_photo_and_discount(owner, app):
    r = _new_product(owner, discount_percent="20", cutout="1", photos=(photo_bytes(), "cam.png"))
    pid = _pid(owner, r)
    html = owner.get(f"/product/{_slug(r)}").get_data(as_text=True)
    assert "$800.00" in html and "$1,000.00" in html and "−20%" in html
    with app.test_request_context():
        from app.models import products
        p = products.get(pid)
        assert len(p["images"]) == 1 and p["images"][0]["filename"].endswith(".webp")
        assert (Path(app.config["UPLOAD_DIR"]) / p["images"][0]["filename"]).exists()


def test_expired_discount_not_applied(owner):
    past = (date.today() - timedelta(days=1)).isoformat()
    r = _new_product(owner, discount_percent="30", discount_ends=past)
    html = owner.get(f"/product/{_slug(r)}").get_data(as_text=True)
    assert "$1,000.00" in html and "$700.00" not in html


def test_invalid_price_rejected(owner):
    r = _new_product(owner, price="abc")
    assert r.status_code == 200 and b"Enter a price" in r.data


def test_non_image_upload_rejected(owner):
    import io
    r = _new_product(owner, photos=(io.BytesIO(b"<script>alert(1)</script>"), "evil.png"))
    pid = _pid(owner, r)
    html = owner.get(f"/altar/products/{pid}").get_data(as_text=True)
    assert "isn't a photo" in html or "0 photos" in owner.get("/altar/products").get_data(as_text=True)


def test_hide_and_delete_product(owner, app):
    r = _new_product(owner, photos=(photo_bytes(), "x.png"))
    pid = _pid(owner, r)
    owner.post(f"/altar/products/{pid}/toggle")
    assert owner.get(f"/product/{_slug(r)}").status_code == 404
    with app.test_request_context():
        from app.models import products
        file = Path(app.config["UPLOAD_DIR"]) / products.get(pid, active_only=False)["images"][0]["filename"]
    owner.post(f"/altar/products/{pid}/delete")
    assert not file.exists()


def test_make_cover_photo(owner, app):
    r = _new_product(owner, photos=[(photo_bytes((200, 0, 0)), "a.png"), (photo_bytes((0, 0, 200)), "b.png")])
    pid = _pid(owner, r)
    with app.test_request_context():
        from app.models import products
        second = products.get(pid)["images"][1]["id"]
    owner.post(f"/altar/products/{pid}/photos/{second}/cover")
    with app.test_request_context():
        assert products.get(pid)["images"][0]["id"] == second


# ---------- studio, portfolio, settings ----------
def test_edit_service(owner):
    owner.post("/altar/services/portrait-sessions", data={"name": "Portraits", "price_prefix": "from", "price_amount": "199", "tagline": "New tagline",
                                          "includes": "A\nB", "icon": "user", "position": "1", "is_active": "1"})
    assert b"from $199" in owner.get("/photography").data


def test_portfolio_upload_shows_publicly(owner):
    owner.post("/altar/portfolio", data={"title": "Smith wedding", "category": "Wedding",
                                         "photos": (photo_bytes(white_border=False), "w.jpg")}, content_type="multipart/form-data")
    assert b"Smith wedding" in owner.get("/portfolio").data


def test_settings_change_site(owner):
    owner.post("/altar/settings", data={"phone": "(403) 555-0000", "instagram": ""})
    html = owner.get("/").get_data(as_text=True)
    assert "(403) 555-0000" in html and 'aria-label="Instagram"' not in html


def test_change_password(owner):
    owner.post("/altar/account", data={"action": "password", "current": PASSWORD, "password": "another-long-pass", "confirm": "another-long-pass"})
    owner.post("/altar/logout")
    r = owner.post("/altar/login", data={"email": "owner@example.com", "password": "another-long-pass"})
    assert r.status_code == 302


def test_product_address_uses_name(owner):
    r1 = _new_product(owner, name="Sony A7 IV")
    r2 = _new_product(owner, name="Sony A7 IV")          # same name → still a unique address
    p1 = owner.get("/product/sony-a7-iv")
    p2 = owner.get("/product/sony-a7-iv-2")
    assert p1.status_code == 200 and p2.status_code == 200
    pid = _pid(owner, r1)
    assert owner.get(f"/product/{pid}").status_code == 404      # number links are not valid


def test_rename_changes_address(owner):
    r = _new_product(owner, name="Old Name")
    pid = _pid(owner, r)
    owner.post("/altar/products/old-name", data={"name": "New Name", "category": "cameras", "price": "10",
                                                "discount_percent": "0", "is_active": "1", "in_stock": "1"})
    assert owner.get("/product/new-name").status_code == 200


def test_admin_addresses_use_names(owner):
    r = _new_product(owner, name="Nikon Z8")
    assert r.headers["Location"].endswith("/altar/products/nikon-z8")
    assert owner.get("/altar/products/nikon-z8").status_code == 200
    assert owner.get(f"/altar/products/{_pid(owner, r)}").status_code == 404
    assert owner.get("/altar/services/weddings-events").status_code == 200



def test_studio_gear_admin(owner):
    from conftest import photo_bytes
    assert b"Studio gear" in owner.get("/altar/services").data
    r = owner.post("/altar/services/gear/new", data={"name": "Godox AD600", "role": "Lighting", "position": "9", "is_active": "1",
                                                     "photo": (photo_bytes(), "light.png")}, content_type="multipart/form-data")
    assert r.headers["Location"].endswith("/altar/services/gear/godox-ad600")
    html = owner.get("/photography").get_data(as_text=True)
    assert "Godox AD600" in html and "Lighting" in html
    owner.post("/altar/services/gear/godox-ad600/delete", follow_redirects=True)
    assert b"Godox AD600" not in owner.get("/photography").data


def test_product_form_has_no_studio_option(owner):
    assert b"Used in our studio" not in owner.get("/altar/products/new").data


def test_portfolio_instagram(owner):
    from conftest import photo_bytes
    owner.post("/altar/portfolio", data={"title": "Eric", "category": "Portrait", "instagram": "https://www.instagram.com/eric.shoots/",
                                         "photos": (photo_bytes(white_border=False), "e.jpg")}, content_type="multipart/form-data")
    html = owner.get("/portfolio").get_data(as_text=True)
    assert 'href="https://instagram.com/eric.shoots"' in html and 'title="@eric.shoots"' in html
    assert "instagram.com/eric.shoots" in owner.get("/photography").get_data(as_text=True)
    assert "instagram.com/eric.shoots" in owner.get("/").get_data(as_text=True)          # recent work on the home page


def test_instagram_cleaning():
    from app.models.portfolio import clean_instagram
    assert clean_instagram("@eric") == "eric"
    assert clean_instagram("instagram.com/eric_99?igsh=x") == "eric_99"
    assert clean_instagram("not a handle!") == ""


def test_popup_add_returns_to_list(owner):
    r = owner.post("/altar/products/new", data={"name": "Pop Up Speaker", "category": "audio", "price": "50", "discount_percent": "0",
                                                "is_active": "1", "in_stock": "1", "_back": "/altar/products"}, content_type="multipart/form-data")
    assert r.headers["Location"].endswith("/altar/products")
    r = owner.post("/altar/products/new", data={"name": "Evil", "category": "audio", "price": "50", "discount_percent": "0",
                                                "_back": "https://evil.example.com"}, content_type="multipart/form-data")
    assert r.headers["Location"].endswith("/altar/products/evil")



def test_recent_work_shows_only_portfolio(owner):
    from conftest import photo_bytes
    owner.post("/altar/portfolio", data={"title": "Eric", "category": "Portrait",
                                         "photos": (photo_bytes(white_border=False), "e.jpg")}, content_type="multipart/form-data")
    for url in ["/", "/photography"]:
        html = owner.get(url).get_data(as_text=True)
        assert "Recent work." in html and html.count('class="gallery-item"') == 1, url
    photo = owner.get("/photography").get_data(as_text=True)
    assert photo.index("How it works") < photo.index('id="portfolio"')


# ---------- currency ----------
def test_currency_change_applies_everywhere(owner):
    s = owner.get("/altar/settings").data
    assert b'value="RWF"' in s and b"Rwandan Franc" in s
    owner.post("/altar/settings", data={"currency": "RWF", "name": "Best Buy 250"})
    home = owner.get("/").data.decode()
    assert "RWF " in home and "Prices in Rwandan Franc (RWF)" in home
    shop = owner.get("/shop").data.decode()
    assert "$" not in shop.split("<main>")[1].split("</main>")[0]
    assert "RWF 299<" in shop or "RWF 299 " in shop   # 299.00 shown with no decimals
    photo = owner.get("/photography").data.decode()
    assert "from RWF 149" in photo
    form = owner.get("/altar/products/new").data.decode()
    assert "Price (RWF)" in form and 'data-symbol="RWF"' in form and 'data-decimals="0"' in form


def test_pounds(owner):
    owner.post("/altar/settings", data={"currency": "GBP"})
    assert "£" in owner.get("/shop").data.decode()


def test_unknown_currency_falls_back(owner):
    owner.post("/altar/settings", data={"currency": "ZZZ"})
    assert b"(USD)" in owner.get("/").data


def test_service_without_amount(owner):
    owner.post("/altar/services/portrait-sessions", data={"name": "Portrait Sessions", "price_prefix": "Ask for a quote",
               "price_amount": "", "icon": "user", "position": "1", "is_active": "1"})
    assert b"Ask for a quote" in owner.get("/photography").data
