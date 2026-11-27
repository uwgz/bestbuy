"""
Giveaways (/admin/giveaways): a random visitor of the website wins a prize, one product or an amount of money.

    + New giveaway   the prize, how many winners, 1 in how many visitors wins, first and last day
    Check a code     the winner brings a code like K7Q-4MZ-9XA-2PD: is it real, and was it already collected?
    Give the prize   marks the code as collected (a product comes off the stock)
    Stop / Resume    no new winners while stopped; codes already won stay valid
"""
from datetime import date

from flask import flash, g, redirect, render_template, request, url_for

from .admin import FormError, amount, audit, bp, login_required, text, today, whole
from .extensions import db
from .models import Giveaway, GiveawayCode, Product, StockMove, clean_code, pretty_code, utcnow


@bp.route("/giveaways")
@login_required
def giveaways():
    code = clean_code(request.args.get("code"))
    found = GiveawayCode.query.filter_by(code=code).first() if code else None
    rows = Giveaway.query.order_by(Giveaway.id.desc()).all()
    products = Product.query.filter(Product.stock > 0).order_by(Product.short).all()
    return render_template("admin/giveaways.html", rows=rows, products=products,
                           checked=pretty_code(code) if code else "", found=found)


def _date(f, name, label):
    try:
        return date.fromisoformat(f.get(name, ""))
    except ValueError:
        raise FormError(f"Choose the {label}.")


@bp.route("/giveaways/new", methods=["POST"])
@login_required
def giveaway_new():
    f = request.form
    try:
        prize = f.get("prize")
        if prize not in ("product", "money"):
            raise FormError("Choose the prize: a product or money.")
        winners = whole(f.get("winners"), "How many winners", 1, 1000)
        chance = whole(f.get("chance"), "1 in how many visitors", 1, 1000000)
        starts, ends = _date(f, "starts_on", "first day"), _date(f, "ends_on", "last day")
        if ends < starts:
            raise FormError("The last day must be on or after the first day.")
        if ends < today():
            raise FormError("The last day can't be in the past.")
        row = Giveaway(prize=prize, winners=winners, chance=chance, starts_on=starts, ends_on=ends, created_by=g.user.id)
        if prize == "product":
            try:
                product = db.session.get(Product, int(f.get("product_id") or 0))
            except ValueError:
                product = None
            if not product:
                raise FormError("Choose the product to give away.")
            if product.stock < winners:
                raise FormError(f"Only {product.stock} {product.short} in stock for {winners} winners. Refill it or choose fewer winners.")
            row.product_id, row.product_name = product.id, product.name
        else:
            row.amount = amount(f.get("amount"), "Amount")
        db.session.add(row)
        db.session.flush()
        what = row.product_name or f"{row.amount:,.0f}"
        audit("giveaway.new", f"#{row.id}: {what}, {winners} winners, 1 in {chance}, {starts}–{ends}")
        db.session.commit()
        flash(f"Giveaway saved: {winners} winner{'s' if winners > 1 else ''}, 1 in {chance} visitors, "
              f"{starts:%b} {starts.day} to {ends:%b} {ends.day}.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("admin.giveaways"))


@bp.route("/giveaways/<int:giveaway_id>/stop", methods=["POST"])
@login_required
def giveaway_stop(giveaway_id):
    row = db.session.get(Giveaway, giveaway_id)
    if row:
        row.is_active = not row.is_active
        audit("giveaway.resume" if row.is_active else "giveaway.stop", f"#{row.id}")
        db.session.commit()
        flash("Giveaway running again." if row.is_active else "Giveaway stopped: no new winners. Codes already won still work.", "success")
    return redirect(url_for("admin.giveaways"))


@bp.route("/giveaways/claim", methods=["POST"])
@login_required
def giveaway_claim():
    """The winner is here: hand over the prize and mark the code as collected."""
    f = request.form
    code = clean_code(f.get("code"))
    try:
        found = GiveawayCode.query.filter_by(code=code).first()
        if not found:
            raise FormError("This code was not made by the website.")
        if found.claimed_at:
            raise FormError("This prize was already collected.")
        customer = text(f, "customer", "the winner's name or phone", limit=120)
        gw = found.giveaway
        if gw.prize == "product":
            product = gw.product
            if not product or product.stock < 1:
                raise FormError("The prize product is out of stock. Refill it first, then give the prize.")
            product.stock -= 1
            found.value = product.cost
            db.session.add(StockMove(product_id=product.id, product_name=product.short, sku=product.sku, kind="giveaway",
                                     qty=-1, unit_cost=product.cost, amount=product.cost, happened_on=today(),
                                     reason=f"Giveaway {found.pretty} to {customer}", created_by=g.user.id))
        else:
            found.value = gw.amount
            db.session.add(StockMove(product_name="Money prize", kind="giveaway", qty=0, amount=gw.amount, happened_on=today(),
                                     reason=f"Giveaway {found.pretty} to {customer}", created_by=g.user.id))
        found.claimed_at, found.claimed_by, found.customer = utcnow(), g.user.id, customer
        audit("giveaway.claim", f"{found.pretty} to {customer}")
        db.session.commit()
        flash(f"Prize given to {customer}. Code {found.pretty} is now used.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("admin.giveaways", code=code))
