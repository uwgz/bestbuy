"""
Best Buy 250 — a simple website: Flask only moves between pages, everything shown comes from data.py.
No login, no database. The cart and "likes" live in the visitor's browser.

Run on your computer:   pip install -r requirements.txt   then   flask --app app run --debug
"""
import hashlib
import os
from pathlib import Path
from urllib.parse import quote

from flask import Flask, abort, render_template, request, url_for

import data
from icons import icon

ROOT = Path(__file__).resolve().parent
STATIC = ROOT / "public" / "static"

app = Flask(__name__, static_folder=str(STATIC), static_url_path="/static", template_folder="templates")
app.config["SEND_FILE_MAX_AGE_DEFAULT"] = 31536000      # files are versioned below, so browsers may keep them

SORTS = {"featured": "Featured", "price-asc": "Price: low to high", "price-desc": "Price: high to low", "name": "Name"}


# ---------------------------------------------------------------- products, ready for the pages
def _product(p, index):
    code = data.CATEGORIES[p["category"]][2]
    price = round(p["price"] * (100 - p["discount"]) / 100) if p["discount"] else p["price"]
    return {**p, "id": index + 1, "sku": f"{code}-{index + 1:04d}", "category_label": data.CATEGORIES[p["category"]][0],
            "icon": data.CATEGORIES[p["category"]][1], "final_price": price, "on_sale": bool(p["discount"]),
            "save": p["price"] - price, "image": p["photos"][0] if p["photos"] else ""}


PRODUCTS = [_product(p, i) for i, p in enumerate(data.PRODUCTS)]
BY_SLUG = {p["slug"]: p for p in PRODUCTS}


def money(value):
    d = data.STORE["decimals"]
    return f'{data.STORE["currency"]} {value:,.{d}f}'


def overview(text):
    """Description -> paragraphs and bullet lists ("- " lines)."""
    blocks = []
    for line in (text or "").splitlines():
        line = line.strip()
        if line.startswith("- "):
            if not blocks or blocks[-1][0] != "ul":
                blocks.append(("ul", []))
            blocks[-1][1].append(line[2:])
        elif line:
            blocks.append(("p", line))
    return blocks


def whatsapp_link(text):
    """wa.me link with a ready message; without a number WhatsApp lets the visitor pick the chat."""
    number = "".join(ch for ch in data.STORE["whatsapp"] if ch.isdigit())
    return f"https://wa.me/{number}?text={quote(text)}" if number else f"https://wa.me/?text={quote(text)}"


# ---------------------------------------------------------------- template helpers
_versions = {}


@app.url_defaults
def _version_static(endpoint, values):
    """Add ?v=<file hash> to /static links, so a new version is never hidden by an old cached copy."""
    if endpoint == "static" and "filename" in values and "v" not in values:
        name = values["filename"]
        if name not in _versions:
            try:
                _versions[name] = hashlib.md5((STATIC / name).read_bytes()).hexdigest()[:10]
            except OSError:
                _versions[name] = (os.environ.get("VERCEL_DEPLOYMENT_ID") or "1")[:10]
        values["v"] = _versions[name]


@app.context_processor
def _globals():
    return {"store": data.STORE, "categories": data.CATEGORIES, "icon": icon, "money": money,
            "whatsapp_link": whatsapp_link, "nav_section": _section()}


def _section():
    ep = request.endpoint or ""
    return "devices" if ep in ("shop", "product", "cart") else "photo" if ep in ("studio",) else ""


app.jinja_env.filters["overview"] = overview


# ---------------------------------------------------------------- pages
@app.route("/")
def home():
    deals = [p for p in PRODUCTS if p["on_sale"]]
    featured = [p for p in PRODUCTS if p["badge"] in ("New", "Best seller", "Pro pick")]
    booking = whatsapp_link(f'Hello {data.STORE["name"]}! I would like to book a photo session.')
    slides = [{**s, "href": booking if s["link"] == "whatsapp" else s["link"], "external": s["link"] == "whatsapp"}
              for s in data.HERO_SLIDES]
    return render_template("home.html", deals=deals[:4], featured=featured[:4], portfolio=data.PORTFOLIO[:3],
                           slides=slides, slide_seconds=data.SLIDE_SECONDS)


@app.route("/shop")
def shop():
    cat = request.args.get("category", "")
    q = request.args.get("q", "").strip()
    sort = request.args.get("sort", "featured")
    items = PRODUCTS
    if cat in data.CATEGORIES:
        items = [p for p in items if p["category"] == cat]
    else:
        cat = ""
    if q:
        words = q.lower().split()
        items = [p for p in items if all(w in f'{p["name"]} {p["short"]} {p["category_label"]} {p["sku"]}'.lower() for w in words)]
    if sort == "price-asc":
        items = sorted(items, key=lambda p: p["final_price"])
    elif sort == "price-desc":
        items = sorted(items, key=lambda p: -p["final_price"])
    elif sort == "name":
        items = sorted(items, key=lambda p: p["short"].lower())
    else:
        sort = "featured"
    counts = {k: sum(p["category"] == k for p in PRODUCTS) for k in data.CATEGORIES}
    return render_template("shop.html", items=items, cat=cat, q=q, sort=sort, sorts=SORTS, counts=counts)


@app.route("/product/<slug>")
def product(slug):
    p = BY_SLUG.get(slug) or abort(404)
    related = [r for r in PRODUCTS if r["category"] == p["category"] and r["slug"] != slug][:4]
    if len(related) < 4:
        related += [r for r in PRODUCTS if r["category"] != p["category"]][: 4 - len(related)]
    ask = whatsapp_link(f'Hello {data.STORE["name"]}! I\'m interested in {p["short"]} ({p["sku"]}, {money(p["final_price"])}).\n'
                        + url_for("product", slug=slug, _external=True))
    return render_template("product.html", p=p, related=related, ask=ask)


@app.route("/cart")
def cart():
    catalog = {p["slug"]: {"short": p["short"], "sku": p["sku"], "price": p["final_price"], "image": p["image"],
                           "stock": p["stock"], "url": url_for("product", slug=p["slug"])} for p in PRODUCTS}
    return render_template("cart.html", catalog=catalog)


@app.route("/photography")
def studio():
    return render_template("studio.html", services=data.SERVICES, portfolio=data.PORTFOLIO)


@app.route("/contact")
def contact():
    return render_template("contact.html")


@app.route("/robots.txt")
def robots():
    return "User-agent: *\nAllow: /\n", 200, {"Content-Type": "text/plain"}


@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.svg")


@app.errorhandler(404)
def not_found(e):
    return render_template("404.html"), 404
