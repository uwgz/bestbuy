import pytest
from app import create_app


@pytest.mark.parametrize("url", ["/", "/shop", "/shop?category=lenses&sort=price_desc", "/shop?q=canon", "/product/noise-cancelling-headphones",
                                 "/photography", "/portfolio", "/book", "/contact", "/cart"])
def test_public_pages(client, url):
    assert client.get(url).status_code == 200


@pytest.mark.parametrize("url", ["/product/2", "/services", "/nope", "/product/does-not-exist"])
def test_old_and_unknown_links_404(client, url):
    r = client.get(url)
    assert r.status_code == 404 and b"Page not found." in r.data and b"Search products" in r.data
    assert r.headers["Cache-Control"] == "no-store"


def test_405_page(client):
    r = client.get("/checkout")
    assert r.status_code == 405 and b"be opened that way" in r.data


def test_413_page(app, client):
    app.config["MAX_CONTENT_LENGTH"] = 10
    r = client.post("/contact", data={"message": "x" * 100})
    assert r.status_code == 413 and b"too big" in r.data


def test_500_page(app, client):
    app.config.update(PROPAGATE_EXCEPTIONS=False)
    @app.route("/boom")
    def boom():
        raise RuntimeError("test")
    r = client.get("/boom")
    assert r.status_code == 500 and b"Something broke on our side." in r.data


def test_400_expired_form(app, client):
    app.config["CSRF_ENABLED"] = True
    r = client.post("/contact", data={"name": "a"})
    assert r.status_code == 400 and b"session expired" in r.data


def test_missing_product_404(client):
    assert client.get("/product/9999").status_code == 404


def test_footer_has_admin_link_but_nav_does_not(client):
    html = client.get("/").get_data(as_text=True)
    footer = html[html.index("site-footer"):]
    header = html[:html.index("</header>")]
    assert "/altar/login" in footer and "/altar" not in header


def test_cart_flow(client):
    client.post("/cart/add/1", data={"qty": 2})
    html = client.get("/cart").get_data(as_text=True)
    assert "$598.00" in html
    client.post("/cart/update/1", data={"qty": 0})
    assert "empty" in client.get("/cart").get_data(as_text=True)


def test_contact_and_booking_saved(client, app):
    r = client.post("/contact", data={"name": "Ann", "email": "a@b.co", "subject": "Prints", "message": "Hello"})
    from urllib.parse import unquote
    assert r.headers["Location"].startswith("https://wa.me/15551234567?text=")
    text = unquote(r.headers["Location"])
    assert "Name: Ann" in text and "Subject: Prints" in text and "Hello" in text
    client.post("/book", data={"name": "Ann", "email": "a@b.co", "service": "portrait-sessions", "date": "2030-01-01"})
    with app.test_request_context():
        from app.models import inbox
        assert len(inbox.messages()) == 1 and len(inbox.bookings()) == 1


def test_stylesheets_and_scripts_exist(client):
    """Every CSS/JS file a page links to must actually load."""
    import re
    for url in ["/", "/altar/login"]:
        html = client.get(url).get_data(as_text=True)
        for asset in re.findall(r'(?:href|src)="(/static/[^"]+\.(?:css|js))"', html):
            assert client.get(asset).status_code == 200, asset


def test_cart_whatsapp_order(client):
    from urllib.parse import unquote
    client.post("/cart/add/2", data={"qty": 2})
    html = client.get("/cart").get_data(as_text=True)
    assert "Request via WhatsApp" in html and 'disabled title="Online checkout coming soon"' in html
    link = html.split('href="https://wa.me/')[1].split('"')[0]
    text = unquote(link.split("?text=")[1].replace("&amp;", "&"))
    assert link.startswith("15551234567") and "2 × Bluetooth Speaker Pulse — $258.00" in text and "Total: $258.00" in text


def test_checkout_disabled(client):
    client.post("/cart/add/2")
    r = client.post("/checkout")
    assert r.headers["Location"].endswith("/cart")
    assert "Speaker" in client.get("/cart").get_data(as_text=True)   # cart kept



def test_photography_gear_not_for_sale(client):
    """Studio gear shows on the Photography page but is not a shop product."""
    photo = client.get("/photography").get_data(as_text=True)
    assert "The gear behind our shots" in photo and "EOS R6 Mark III" in photo and "Main camera" in photo
    shop = client.get("/shop").get_data(as_text=True)
    assert "EOS R6" not in shop and "Joby" not in shop and "Noise-Cancelling" in shop


def test_photography_page_has_portfolio_after_how_it_works(client):
    html = client.get("/photography").get_data(as_text=True)
    assert 'id="portfolio"' not in html and 'class="gallery-item"' not in html   # empty portfolio → no section
    # (shown once portfolio photos are uploaded — see test_admin.test_portfolio_instagram)


def test_home_recent_work_only_from_portfolio(client):
    html = client.get("/").get_data(as_text=True)
    assert "Recent work." not in html and 'class="gallery-item"' not in html   # nothing uploaded → hidden


def test_currency_formatting():
    from app.currency import format_amount, plain, CURRENCIES
    assert "RWF" in CURRENCIES and len(CURRENCIES) > 140
    assert format_amount(12000, "RWF") == "RWF 12,000"
    assert format_amount(1299.5, "USD") == "$1,299.50"
    assert format_amount(49.99, "GBP") == "£49.99"
    assert plain(12000, "RWF") == "12000" and plain(5, "EUR") == "5.00"


def test_whatsapp_button(client, owner):
    home = client.get("/").get_data(as_text=True)
    assert 'class="wa-float"' in home and "https://wa.me/15551234567?text=Hello" in home
    assert 'class="wa-float"' not in owner.get("/altar/").get_data(as_text=True)   # not in the admin
    assert 'class="wa-float"' not in client.get("/no-such-page").get_data(as_text=True)


def test_static_files_are_versioned_and_cached(client):
    import re
    html = client.get("/").get_data(as_text=True)
    css = re.search(r'href="(/static/css/site\.css\?v=[0-9a-f]{10})"', html)
    assert css, "stylesheet link should carry ?v=<hash>"
    r = client.get(css.group(1))
    assert r.status_code == 200 and "max-age=31536000" in r.headers.get("Cache-Control", "")


def test_loader_on_every_page(client, owner):
    for page in (client.get("/"), client.get("/shop"), owner.get("/altar/")):
        html = page.get_data(as_text=True)
        assert 'id="page-loader"' in html and 'class="loader-mark"' in html and "js/loader.js" in html


def test_brand_files_exist(client):
    for name in ("logo-mark.svg", "logo-mark-white.svg", "app-icon.svg", "favicon-32.png", "icon-192.png", "icon-512.png",
                 "logo-on-dark.png", "logo-on-light.png", "logo-transparent.png", "social-profile-1080.png"):
        assert client.get(f"/static/img/brand/{name}").status_code == 200, name
    assert client.get("/static/favicon.svg").status_code == 200
    assert client.get("/static/apple-touch-icon.png").status_code == 200


def test_logo_animation_in_top_bar_and_error_pages(client):
    home = client.get("/").get_data(as_text=True)
    top = home.split('class="logo-mark"')[1].split("</svg>")[0]
    assert 'repeatCount="indefinite"' in top and "#ff3b30" in top               # top bar: the lines light up red in turn
    missing = client.get("/no-such-page").get_data(as_text=True)
    assert 'class="error-mark"' in missing and 'repeatCount="indefinite"' in missing


def test_new_site_starts_empty(tmp_path):
    """No sample products, services, photos or made-up contact details on a fresh install."""
    fresh = create_app("testing", INSTANCE_DIR=tmp_path / "fresh")
    c = fresh.test_client()
    assert "No products yet" in c.get("/shop").get_data(as_text=True)
    home = c.get("/").get_data(as_text=True)
    assert "555" not in home and "Main Street" not in home and "wa.me" not in home
    contact = c.get("/contact").get_data(as_text=True)
    assert "Send message" in contact and "Send via WhatsApp" not in contact
    assert c.get("/photography").status_code == 200
    assert c.get("/altar/login").headers["Location"].endswith("/altar/setup")      # first visit: create the owner


def test_product_page_layout(app, client):
    from app.db import execute
    from app.models import settings
    with app.app_context():
        settings.save({"whatsapp_orders": "250 788 000 000"})
        execute("INSERT INTO products (slug, name, category, description, price_cents, discount_percent, discount_ends) "
                "VALUES ('flip-14', 'Flip 14', 'computers', ?, 100000, 10, '2099-11-29')",
                ("A light 2-in-1 laptop.\n- 16GB RAM\n- 512GB SSD",))
    html = client.get("/product/flip-14").get_data(as_text=True)
    assert 'id="pd-share"' in html and 'id="pd-like"' in html
    assert "Sale ends: <span>November 29, 2099</span>" in html
    assert "https://wa.me/250788000000?text=" in html and "Pick up" in html
    assert "Add to cart" in html and "1-year warranty" in html and "extended" not in html
    assert "<p>A light 2-in-1 laptop.</p>" in html and "<li>16GB RAM</li><li>512GB SSD</li>" in html


def test_overview_splits_paragraphs_and_bullets():
    from app.helpers import overview, long_date
    assert overview("One\ntwo\n\n• a\n* b\nThree") == [("p", "One two"), ("ul", ["a", "b"]), ("p", "Three")]
    assert overview("") == [] and long_date("") == "" and long_date("2026-01-05") == "January 5, 2026"
