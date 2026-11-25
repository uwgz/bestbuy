"""Home page, contact form and giveaway."""
import re
import secrets

from flask import abort, flash, g, jsonify, redirect, render_template, request, session, url_for

from . import bp
from ...models import giveaways, inbox, portfolio, products, services, settings

# link previews, crawlers and scripts never win
_NOT_A_PERSON = re.compile(r"bot|crawl|spider|slurp|preview|facebookexternalhit|whatsapp|telegram|curl|wget|python-requests|httpclient", re.I)

# In-store gallery at the bottom of the home page (photos in public/static/img/hero/)
GALLERY = [
    {"image": "img/hero/desk-electronics.jpg", "position": "60% 50%", "eyebrow": "Electronics",
     "title": "Everything for your setup.", "alt": "Laptop, tablet, VR headset and smartwatch on a desk",
     "button": ("Shop devices", "shop.shop", {})},
    {"image": "img/hero/canon-r6-in-store.jpg", "position": "50% 40%", "eyebrow": "In store now",
     "title": "Hold it before you buy it.", "alt": "Camera on display in store",
     "button": ("Browse cameras", "shop.shop", {"category": "cameras"})},
    {"image": "img/hero/hp-omnibook-on-wood.jpg", "position": "50% 50%", "eyebrow": "Edit anywhere",
     "title": "Edit on location.", "alt": "Laptop on a wooden table",
     "button": ("Browse computers", "shop.shop", {"category": "computers"})},
]


@bp.route("/")
def home():
    spotlight = products.list_products(on_home=True)
    weddings = services.get_by_slug("weddings-events")       # a "Weddings & Events" service with photos, if any
    return render_template(
        "main/home.html",
        full_tiles=spotlight[:2],
        grid_tiles=spotlight[2:],
        shelf=products.list_products(sort="newest")[:8],
        wedding_photo=(weddings["images"][0]["url"] if weddings and weddings["images"] else None),
        gallery=GALLERY,
        work=portfolio.recent_work(6),
    )


@bp.route("/contact", methods=["GET", "POST"])
def contact():
    if request.method == "POST":
        f = request.form
        name, email, message = f.get("name", "").strip(), f.get("email", "").strip(), f.get("message", "").strip()
        subject = f.get("subject", "").strip()
        if not (name and message):
            flash("Please fill in your name and message.", "error")
            return render_template("main/contact.html", form=f)
        inbox.add_message(name, email, subject, message)          # copy kept in the admin Inbox
        text = [f"Hello {settings.business()['name']}!", "", f"Name: {name}"]
        if email:
            text.append(f"Email: {email}")
        if subject:
            text.append(f"Subject: {subject}")
        text += ["", message]
        link = settings.whatsapp_link("\n".join(text))
        if link:
            return redirect(link)                                     # opens WhatsApp with the message ready
        flash("Thanks for reaching out! We'll get back to you soon.", "success")
        return redirect(url_for("main.contact"))
    return render_template("main/contact.html", form={})



# ---------------------------------------------------------------- giveaway
@bp.route("/giveaway/check", methods=["POST"])
def giveaway_check():
    """Asked by the page (site.js) while a giveaway runs: has this visitor just won?"""
    test = session.get("giveaway_test")
    if test and giveaways.test_giveaway(test):
        visitor = session.setdefault("visitor", secrets.token_urlsafe(12))
        win = giveaways.try_win(visitor, test_token=test)      # "Try it yourself": anyone with the link, staff too
    else:
        session.pop("giveaway_test", None)
        if g.get("user") or _NOT_A_PERSON.search(request.headers.get("User-Agent", "")):
            return jsonify(won=False)          # staff signed in to the admin, and robots, can't win
        visitor = session.setdefault("visitor", secrets.token_urlsafe(12))
        win = giveaways.try_win(visitor)
    if not win:
        return jsonify(won=False, live=bool(giveaways.running()))
    name = settings.business()["name"]
    device = products.get(win["product_id"]) if win.get("product_id") else None
    return jsonify(
        # tapping the prize name opens the shop with the device's name in the search bar
        link=url_for("shop.shop", q=device["name"]) if device else None,
        won=True, test=win["is_test"], code=win["code"], prize=win["prize"], claim_by=win["claim_by"], days=giveaways.CLAIM_DAYS,
        whatsapp=settings.whatsapp_link(f"Hi {name}! I won the giveaway: {win['prize']}. My code is {win['code']}."),
        rules=url_for("main.giveaway_rules"), contact=url_for("main.contact"))


@bp.route("/giveaway/try/<token>")
def giveaway_try(token):
    """Link from the admin's "Try it yourself": this browser wins the test prize on the next page."""
    if not giveaways.test_giveaway(token):
        abort(410)    # an old test link
    session["giveaway_test"] = token
    return redirect(url_for("main.home"))


@bp.route("/giveaway-rules")
def giveaway_rules():
    return render_template("main/giveaway_rules.html", claim_days=giveaways.CLAIM_DAYS)
