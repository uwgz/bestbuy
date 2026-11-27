import re

import pytest

import app as site
import data


@pytest.fixture
def client():
    site.app.config["TESTING"] = True
    return site.app.test_client()


def test_every_category_has_at_least_two_products():
    for key in data.CATEGORIES:
        assert sum(p["category"] == key for p in data.PRODUCTS) >= 2, key


def test_product_data_is_complete():
    slugs = [p["slug"] for p in data.PRODUCTS]
    assert len(slugs) == len(set(slugs))
    for p in data.PRODUCTS:
        assert p["category"] in data.CATEGORIES and p["photos"] and p["price"] > 0
        assert all(u.startswith(("https://images.unsplash.com/", "/static/")) for u in p["photos"])
        assert len(p["short"].split()) <= 4, p["short"]
        assert len([w for w in p["name"].split() if w.strip("-")]) <= 20, p["name"]


@pytest.mark.parametrize("url", ["/", "/shop", "/cart", "/photography", "/contact"] +
                         [f"/shop?category={k}" for k in data.CATEGORIES] +
                         [f"/product/{p['slug']}" for p in data.PRODUCTS])
def test_pages_open(client, url):
    r = client.get(url)
    assert r.status_code == 200
    html = r.get_data(as_text=True)
    assert "css/app.css?v=" in html and "js/app.js?v=" in html
    title = html.split("<title>")[1].split("</title>")[0]
    assert "<" not in title


def test_category_pages_show_their_products(client):
    for key in data.CATEGORIES:
        html = client.get(f"/shop?category={key}").get_data(as_text=True)
        for p in data.PRODUCTS:
            assert (f'/product/{p["slug"]}"' in html) == (p["category"] == key)


def test_search_and_sort(client):
    html = client.get("/shop?q=macbook").get_data(as_text=True)
    assert "MacBook Air" in html and "iPhone 17 Pro" not in html
    html = client.get("/shop?sort=price-asc").get_data(as_text=True)
    prices = [int(x.replace(",", "")) for x in re.findall(r'text-sale">RWF ([\d,]+)|font-semibold">RWF ([\d,]+)', html) for x in x if x]
    assert prices == sorted(prices)


def test_product_page_parts(client):
    p = data.PRODUCTS[3]       # MacBook Air: on sale, 2 photos
    html = client.get(f"/product/{p['slug']}").get_data(as_text=True)
    for part in ('data-share', 'data-like=', 'data-dot', 'WhatsApp', 'Pick up', 'data-add=', '1-year warranty',
                 'About this product', '<li>Apple M4 chip', 'Save RWF', 'SKU LAP-0004'):
        assert part in html, part
    assert "https://wa.me/?text=" in html            # no number set yet: WhatsApp lets you pick the chat


def test_cart_page_has_catalog(client):
    html = client.get("/cart").get_data(as_text=True)
    assert "window.CATALOG" in html and data.PRODUCTS[0]["slug"] in html


def test_no_login_or_admin(client):
    for url in ("/altar", "/admin", "/login"):
        assert client.get(url).status_code == 404


def test_unknown_product_is_404(client):
    r = client.get("/product/nope")
    assert r.status_code == 404 and b"This page isn" in r.data


def test_studio_cards_have_photos_and_portfolio_has_instagram(client):
    html = client.get("/photography").get_data(as_text=True)
    for s in data.SERVICES:
        assert s["photo"].replace("&", "&amp;") in html
    assert html.count('aria-label="See on Instagram"') == len(data.PORTFOLIO)
    assert 'href="https://www.instagram.com/"' in html


def test_home_slideshow(client):
    html = client.get("/").get_data(as_text=True)
    n = len(data.HERO_SLIDES)
    assert html.count("data-slide ") == n and html.count("data-slide data-current") == 1
    assert html.count("data-slide-dot=") == n and f'data-seconds="{data.SLIDE_SECONDS}"' in html
    assert "Shop now" in html and "Book now" in html and "https://wa.me/" in html
