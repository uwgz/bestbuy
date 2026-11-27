import re

import pytest

from bestbuy import seed
from bestbuy.extensions import db
from bestbuy.models import Category, HeroSlide, PortfolioItem, Product, Service, Setting

PAGES = ["/", "/shop", "/cart", "/photography", "/contact"]


def test_starting_content_is_loaded(app):
    assert Category.query.count() == len(seed.CATEGORIES)
    assert Product.query.count() == len(seed.PRODUCTS)
    assert Service.query.count() == len(seed.SERVICES)
    assert PortfolioItem.query.count() == len(seed.PORTFOLIO)
    assert HeroSlide.query.count() == len(seed.HERO_SLIDES)
    assert seed.load_demo() == []                       # running it again adds nothing


def test_every_category_has_at_least_two_products(app):
    for c in Category.query:
        assert len(c.products) >= 2, c.key


def test_product_fields(app):
    p = Product.query.filter_by(slug="macbook-air-13-m4-16gb-512gb").one()
    assert p.sku == f"LAP-{p.id:04d}" and p.category_label == "Laptops & Computers"
    assert len(p.photos) == 2 and p.image == p.photos[0]
    assert p.on_sale and p.final_price == 1605500 and p.save == 84500
    for p in Product.query:
        assert len(p.short.split()) <= 4 and len([w for w in p.name.split() if w.strip("-")]) <= 20


@pytest.mark.parametrize("url", PAGES)
def test_pages_open(client, url):
    r = client.get(url)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "css/app.css?v=" in html and "js/app.js?v=" in html
    assert "<" not in html.split("<title>")[1].split("</title>")[0]


def test_every_product_and_category_page_opens(client):
    for p in Product.query:
        assert client.get(f"/product/{p.slug}").status_code == 200, p.slug
    for c in Category.query:
        html = client.get(f"/shop?category={c.key}").get_data(as_text=True)
        for p in Product.query:
            assert (f'/product/{p.slug}"' in html) == (p.category == c.key)


def test_search_and_sort(client):
    html = client.get("/shop?q=macbook").get_data(as_text=True)
    assert "MacBook Air" in html and "iPhone 17 Pro" not in html
    html = client.get("/shop?sort=price-asc").get_data(as_text=True)
    prices = [int(x.replace(",", "")) for pair in re.findall(r'text-sale">RWF ([\d,]+)|font-semibold">RWF ([\d,]+)', html)
              for x in pair if x]
    assert prices == sorted(prices)


def test_product_page_parts(client):
    html = client.get("/product/macbook-air-13-m4-16gb-512gb").get_data(as_text=True)
    for part in ("data-share", "data-like=", "data-dot", "WhatsApp", "Pick up", "data-add=", "1-year warranty",
                 "About this product", "<li>Apple M4 chip", "Save RWF 84,500", "RWF 1,605,500"):
        assert part in html, part
    assert "https://wa.me/?text=" in html            # no number set yet: WhatsApp lets you pick the chat


def test_changes_in_the_database_show_on_the_site(client):
    """Nothing is hard-coded: change a row and the page follows."""
    p = Product.query.filter_by(slug="playstation-5-dualsense-controller-white").one()
    p.short, p.price = "DualSense White", 99000
    db.session.add(Setting(key="whatsapp", value="250 788 123 456"))
    db.session.add(Setting(key="address", value="KN 4 Ave, Kigali"))
    db.session.commit()
    html = client.get(f"/product/{p.slug}").get_data(as_text=True)
    assert "DualSense White" in html and "RWF 99,000" in html and "https://wa.me/250788123456?text=" in html
    assert "KN 4 Ave, Kigali" in client.get("/contact").get_data(as_text=True)
    p.is_active = False
    db.session.commit()
    assert client.get(f"/product/{p.slug}").status_code == 404
    assert p.slug not in client.get("/shop").get_data(as_text=True)


def test_home_slideshow(client):
    html = client.get("/").get_data(as_text=True)
    n = HeroSlide.query.count()
    assert html.count("data-slide ") == n and html.count("data-slide data-current") == 1
    assert html.count("data-slide-dot=") == n and 'data-seconds="6"' in html
    assert "Shop now" in html and "Book now" in html


def test_studio_cards_have_photos_and_portfolio_has_instagram(client):
    html = client.get("/photography").get_data(as_text=True)
    for s in Service.query:
        assert s.photo.replace("&", "&amp;") in html
    assert html.count('aria-label="See on Instagram"') == PortfolioItem.query.count()


def test_cart_page_has_catalog(client):
    html = client.get("/cart").get_data(as_text=True)
    assert "window.CATALOG" in html and '"price": 1605500' in html


def test_unknown_pages_are_404(client):
    for url in ("/product/nope", "/altar", "/admin", "/login"):
        assert client.get(url).status_code == 404


def test_neon_address_uses_psycopg(monkeypatch):
    from bestbuy import config
    monkeypatch.setenv("DATABASE_URL", "postgres://u:p@ep-x-pooler.neon.tech/neondb?sslmode=require")
    url = config.database_url()
    assert url == "postgresql+psycopg://u:p@ep-x-pooler.neon.tech/neondb?sslmode=require"
    assert config.engine_options(url)["connect_args"] == {"prepare_threshold": None}
