"""The public pages. Everything they show comes from the database."""
import hashlib
import secrets
from urllib.parse import quote

from flask import abort, current_app, jsonify, render_template, request, session, url_for
from sqlalchemy.exc import IntegrityError

from .extensions import db
from .icons import icon
from .models import STORE_DEFAULTS, Category, GearItem, Giveaway, GiveawayCode, HeroSlide, PortfolioItem, Product, Service, Setting, new_code

SORTS = {"featured": "Featured", "price-asc": "Price: low to high", "price-desc": "Price: high to low", "name": "Name"}
FEATURED_BADGES = ("New", "Best seller", "Pro pick")


# ---------------------------------------------------------------- helpers used by the pages
def money(value):
    store = Setting.store()
    return f'{store["currency"]} {value:,.{store["decimals"]}f}'


def cad(value):
    """Gear prices, in Canadian dollars: $1,250 CAD or $1,250.50 CAD"""
    return f"${value:,.2f}".replace(".00", "") + " CAD"


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


# ---------------------------------------------------------------- giveaway draw
def giveaway_on():
    """The giveaways running today, as "3,4" ("" = none). The page asks for a draw only when one is new to it."""
    try:
        return ",".join(str(gw.id) for gw in Giveaway.live())
    except Exception:
        db.session.rollback()
        return ""


def _visitor():
    """The visitor's internet address, hashed: one win per address and giveaway, nothing personal kept."""
    address = (request.headers.get("X-Forwarded-For") or request.remote_addr or "").split(",")[0].strip()
    return hashlib.sha256(f"{current_app.secret_key}|{address}".encode()).hexdigest()[:32]


def draw():
    """Each visitor is drawn once per giveaway; one in `chance` wins a code while codes are left."""
    drawn = list(session.get("giveaways_drawn", []))
    visitor = _visitor()
    for gw in Giveaway.live():
        if gw.id in drawn:
            continue
        drawn.append(gw.id)
        if GiveawayCode.query.filter_by(giveaway_id=gw.id, visitor=visitor).first():
            continue                                    # this address already won this one
        if secrets.randbelow(gw.chance) != 0:
            continue
        locked = db.session.query(Giveaway).filter_by(id=gw.id).with_for_update().one()   # two winners at once
        if GiveawayCode.query.filter_by(giveaway_id=gw.id).count() >= locked.winners:
            db.session.rollback()
            continue
        for _ in range(5):
            try:
                row = GiveawayCode(giveaway_id=gw.id, code=new_code(), visitor=visitor)
                db.session.add(row)
                db.session.commit()
                break
            except IntegrityError:                      # the same code twice: try another
                db.session.rollback()
        else:
            continue
        session["giveaways_drawn"] = drawn[-50:]
        session.permanent = True
        return row
    session["giveaways_drawn"] = drawn[-50:]
    session.permanent = True
    return None


# ---------------------------------------------------------------- pages
def init_app(app):
    app.jinja_env.filters["overview"] = overview

    @app.context_processor
    def _globals():
        try:
            store, categories = Setting.store(), Category.as_dict()
        except Exception:                      # database unreachable: pages (e.g. the error page) still show
            db.session.rollback()
            store, categories = dict(STORE_DEFAULTS), {}
        return {"store": store, "categories": categories, "icon": icon, "money": money, "cad": cad,
                "whatsapp_link": whatsapp_link, "nav_section": _section(request.endpoint), "giveaway_on": giveaway_on}

    @app.route("/giveaway/draw", methods=["POST"])
    def giveaway_draw():
        if request.headers.get("X-Requested-With") != "fetch":      # only the page's own script
            abort(400)
        won = draw()
        if not won:
            return jsonify(won=False)
        gw, store = won.giveaway, Setting.store()
        ends = f"{gw.ends_on:%A, %B} {gw.ends_on.day}"
        if gw.prize == "product":
            prize = {"kind": "product", "name": gw.product_name,
                     "url": url_for("shop", q=gw.product.short if gw.product else gw.product_name)}
        else:
            prize = {"kind": "money", "name": money(gw.amount), "url": ""}
        message = f'Hello {store["name"]}! I won the website giveaway ({prize["name"]}). My code is {won.pretty}.'
        return jsonify(won=True, code=won.pretty, prize=prize, ends=ends, whatsapp=whatsapp_link(message) if store["whatsapp"] else "")

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
        catalog = {p.slug: {"short": p.short, "sku": p.sku, "price": float(p.final_price), "was": float(p.price),
                            "discount": p.discount if p.on_sale else 0, "image": p.image,
                            "stock": p.stock, "url": url_for("product", slug=p.slug)} for p in active_products()}
        return render_template("cart.html", catalog=catalog)

    @app.route("/photography")
    def studio():
        services = Service.query.filter_by(is_active=True).order_by(Service.position, Service.id).all()
        portfolio = PortfolioItem.query.filter_by(is_active=True).order_by(PortfolioItem.position, PortfolioItem.id).all()
        gear = GearItem.query.filter_by(is_active=True).order_by(GearItem.position, GearItem.id).all()
        return render_template("studio.html", services=services, portfolio=portfolio, gear=gear)

    @app.route("/contact")
    def contact():
        return render_template("contact.html")

    @app.route("/robots.txt")
    def robots():
        return "User-agent: *\nAllow: /\n", 200, {"Content-Type": "text/plain"}

    @app.route("/favicon.ico")
    def favicon():
        return app.send_static_file("favicon.svg")

    # ---------- error pages: one friendly page for every kind of error ----------
    from werkzeug.exceptions import HTTPException

    ERRORS = {
        400: ("Something in that request wasn't right.", "Go back, refresh the page and try again."),
        401: ("You need to sign in first.", "Sign in, then open the page again."),
        403: ("You can't open this page.", "If you think you should, ask the shop's owner."),
        404: ("This page isn't here.", "It may have moved, or the link has a typo."),
        405: ("That doesn't work here.", "Go back and use the page's own buttons."),
        413: ("That file is too big.", "Choose a smaller photo (4 MB at most) and try again."),
        429: ("Too many tries.", "Wait a minute, then try again."),
        500: ("Something went wrong on our side.", "It's not you. Try again in a moment, or message us on WhatsApp."),
        502: ("We couldn't reach a service we need.", "Try again in a moment."),
        503: ("We're back in a moment.", "The site is being updated. Try again in a minute."),
    }

    def error_page(code, detail=None):
        title, text = ERRORS.get(code, ERRORS[500] if code >= 500 else ERRORS[400])
        if detail and code == 400 and "Bad Request" not in detail and "browser (or proxy)" not in detail:
            text = detail                           # our own words, e.g. "This form expired. …"
        try:
            return render_template("error.html", code=code, title=title, text=text,
                                   in_admin=request.path.startswith("/admin")), code
        except Exception:                           # even the page failed: plain words, nothing else needed
            return (f"<!doctype html><meta charset=utf-8><title>{title}</title>"
                    f"<body style='font:17px system-ui;text-align:center;padding:15vh 20px'><h1>{title}</h1>"
                    f"<p>{text}</p><p><a href='/'>Go to the home page</a></p>"), code

    @app.errorhandler(HTTPException)
    def http_error(e):
        if e.code and e.code < 400:                 # redirects and the like are not errors
            return e
        return error_page(e.code or 500, e.description)

    @app.errorhandler(Exception)
    def server_error(e):
        if isinstance(e, HTTPException):
            return http_error(e)
        if app.debug or app.testing:                # on your computer and in tests: show the real error
            raise e
        try:
            db.session.rollback()                   # leave the database ready for the next visitor
        except Exception:
            pass
        app.logger.exception("Unexpected error on %s", request.path)   # shows in Vercel's logs
        return error_page(500)
