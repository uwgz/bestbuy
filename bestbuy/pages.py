"""The public pages. Everything they show comes from the database."""
from urllib.parse import quote

from flask import abort, render_template, request, url_for

from .icons import icon
from .models import Category, HeroSlide, PortfolioItem, Product, Service, Setting

SORTS = {"featured": "Featured", "price-asc": "Price: low to high", "price-desc": "Price: high to low", "name": "Name"}
FEATURED_BADGES = ("New", "Best seller", "Pro pick")


# ---------------------------------------------------------------- helpers used by the pages
def money(value):
    store = Setting.store()
    return f'{store["currency"]} {value:,.{store["decimals"]}f}'


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
    number = "".join(ch for ch in Setting.store()["whatsapp"] if ch.isdigit())
    return f"https://wa.me/{number}?text={quote(text)}"


def active_products():
    return Product.query.filter_by(is_active=True).order_by(Product.position, Product.id).all()


def _section(endpoint):
    return "devices" if endpoint in ("shop", "product", "cart") else "photo" if endpoint == "studio" else ""


# ---------------------------------------------------------------- pages
def init_app(app):
    app.jinja_env.filters["overview"] = overview

    @app.context_processor
    def _globals():
        return {"store": Setting.store(), "categories": Category.as_dict(), "icon": icon, "money": money,
                "whatsapp_link": whatsapp_link, "nav_section": _section(request.endpoint)}

    @app.route("/")
    def home():
        products = active_products()
        deals = [p for p in products if p.on_sale][:4]
        featured = [p for p in products if p.badge in FEATURED_BADGES][:4]
        booking = whatsapp_link(f'Hello {Setting.store()["name"]}! I would like to book a photo session.')
        slides = [{"photo": s.photo, "label": s.label, "text": s.text, "button": s.button,
                   "href": booking if s.link == "whatsapp" else s.link, "external": s.link == "whatsapp"}
                  for s in HeroSlide.query.filter_by(is_active=True).order_by(HeroSlide.position, HeroSlide.id)]
        portfolio = PortfolioItem.query.filter_by(is_active=True).order_by(PortfolioItem.position).limit(3).all()
        return render_template("home.html", deals=deals, featured=featured, portfolio=portfolio,
                               slides=slides, slide_seconds=Setting.store()["slide_seconds"])

    @app.route("/shop")
    def shop():
        categories = Category.as_dict()
        cat = request.args.get("category", "")
        q = request.args.get("q", "").strip()
        sort = request.args.get("sort", "featured")
        everything = active_products()
        items = everything
        if cat in categories:
            items = [p for p in items if p.category == cat]
        else:
            cat = ""
        if q:
            words = q.lower().split()
            items = [p for p in items if all(w in f"{p.name} {p.short} {p.category_label} {p.sku}".lower() for w in words)]
        if sort == "price-asc":
            items = sorted(items, key=lambda p: p.final_price)
        elif sort == "price-desc":
            items = sorted(items, key=lambda p: -p.final_price)
        elif sort == "name":
            items = sorted(items, key=lambda p: p.short.lower())
        else:
            sort = "featured"
        counts = {k: sum(p.category == k for p in everything) for k in categories}
        return render_template("shop.html", items=items, cat=cat, q=q, sort=sort, sorts=SORTS, counts=counts)

    @app.route("/product/<slug>")
    def product(slug):
        p = Product.query.filter_by(slug=slug, is_active=True).first() or abort(404)
        others = [r for r in active_products() if r.id != p.id]
        related = [r for r in others if r.category == p.category][:4]
        related += [r for r in others if r.category != p.category][: 4 - len(related)]
        ask = whatsapp_link(f'Hello {Setting.store()["name"]}! I\'m interested in {p.short} ({p.sku}, {money(p.final_price)}).\n'
                            + url_for("product", slug=slug, _external=True))
        return render_template("product.html", p=p, related=related, ask=ask)

    @app.route("/cart")
    def cart():
        catalog = {p.slug: {"short": p.short, "sku": p.sku, "price": float(p.final_price), "image": p.image,
                            "stock": p.stock, "url": url_for("product", slug=p.slug)} for p in active_products()}
        return render_template("cart.html", catalog=catalog)

    @app.route("/photography")
    def studio():
        services = Service.query.filter_by(is_active=True).order_by(Service.position, Service.id).all()
        portfolio = PortfolioItem.query.filter_by(is_active=True).order_by(PortfolioItem.position, PortfolioItem.id).all()
        return render_template("studio.html", services=services, portfolio=portfolio)

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
