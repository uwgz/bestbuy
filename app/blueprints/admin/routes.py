"""
Admin panel at /altar — sign in, then manage the shop and studio.

    /altar/login        sign in (linked quietly from the site footer)
    /altar/setup        create the first owner account (only while no account exists)
    /altar/             dashboard
"""
from datetime import date

from flask import abort, current_app, flash, g, redirect, render_template, request, url_for

from . import bp
from .forms import FormError, product_from_form, sale_from_form, service_from_form
from ... import currency, images
from ...models import gear, giveaways, inbox, portfolio, products, sales, services, settings, users
from ...security import (clear_failures, login_required, login_user, logout_user,
                         record_failure, too_many_attempts)


def _back(default):
    """Pop-up forms send the page they were opened from; return there after saving."""
    back = request.form.get("_back", "")
    return back if back.startswith("/altar") and not back.startswith("//") else default


def _safe_next(target):
    return target if target and target.startswith("/altar") and not target.startswith("//") else url_for("admin.dashboard")


def _save_photos(files, folder, cutout=False):
    """Save every uploaded photo; returns (saved filenames, error messages)."""
    saved, errors = [], []
    for f in files:
        if not f or not f.filename:
            continue
        try:
            saved.append(images.save_upload(f, folder, cutout=cutout))
        except images.ImageError as e:
            errors.append(f"{f.filename}: {e}")
    return saved, errors


@bp.context_processor
def admin_context():
    if g.get("user"):
        return {"unread": inbox.unread_counts()}
    return {}


# ======================================================================
#  Sign in / out
# ======================================================================
@bp.route("/login", methods=["GET", "POST"])
def login():
    if users.count() == 0:
        return redirect(url_for("admin.setup"))
    if g.user:
        return redirect(url_for("admin.dashboard"))
    if request.method == "POST":
        if too_many_attempts():
            flash("Too many attempts. Please wait 15 minutes and try again.", "error")
            return render_template("admin/login.html", email=request.form.get("email", "")), 429
        user = users.authenticate(request.form.get("email"), request.form.get("password"))
        if user:
            clear_failures()
            login_user(user)
            return redirect(_safe_next(request.args.get("next")))
        record_failure()
        flash("That email and password don't match.", "error")
        return render_template("admin/login.html", email=request.form.get("email", "")), 401
    return render_template("admin/login.html", email="")


@bp.route("/setup", methods=["GET", "POST"])
def setup():
    """First run only: create the owner account."""
    if users.count() > 0:
        return redirect(url_for("admin.login"))
    if request.method == "POST":
        f = request.form
        email, name = f.get("email", "").strip(), f.get("name", "").strip()
        error = None if (email and "@" in email and name) else "Enter your name and a valid email."
        error = error or users.validate_password(f.get("password"), f.get("confirm"))
        if error:
            flash(error, "error")
            return render_template("admin/setup.html", form=f)
        users.create(email, name, f["password"])
        login_user(users.authenticate(email, f["password"]))
        flash("Welcome! Your owner account is ready.", "success")
        return redirect(url_for("admin.dashboard"))
    return render_template("admin/setup.html", form={})


@bp.route("/logout", methods=["POST"])
def logout():
    logout_user()
    flash("You're signed out.", "info")
    return redirect(url_for("admin.login"))


# ======================================================================
#  Dashboard
# ======================================================================
@bp.route("/")
@login_required
def dashboard():
    return render_template("admin/dashboard.html", counts=products.counts(), hosting_warnings=_hosting_warnings(),
                           money=sales.summary(), recent_sales=sales.recent(6),
                           on_sale=products.list_products(active_only=False, on_sale=True),
                           recent_bookings=inbox.bookings()[:5], recent_messages=inbox.messages()[:5],
                           services_count=len(services.list_services(active_only=False)),
                           portfolio_count=len(portfolio.list_items()))


def _sale_products():
    """Products for the 'Record a sale' pop-up: in stock first, then by name."""
    items = products.list_products(active_only=False)
    return sorted(items, key=lambda p: (p["stock_qty"] <= 0, p["short"].lower()))


# ======================================================================
#  Sales
# ======================================================================
@bp.route("/sales", methods=["GET", "POST"])
@login_required
def sales_page():
    if request.method == "POST":
        try:
            data = sale_from_form(request.form)
            sales.record(user_id=g.user["id"], **data)
            flash("Sale recorded.", "success")
        except (FormError, ValueError) as e:
            flash(str(e), "error")
        return redirect(_back(url_for("admin.sales_page")))
    return render_template("admin/sales.html", items=sales.recent(), money=sales.summary(),
                           sale_products=_sale_products(), today=date.today().isoformat())


@bp.route("/sales/<int:sale_id>/delete", methods=["POST"])
@login_required
def sale_delete(sale_id):
    if sales.delete(sale_id):
        flash("Sale removed and its units put back in stock.", "success")
    return redirect(_back(url_for("admin.sales_page")))


def _hosting_warnings():
    """On Vercel, local files vanish: say so if the database or photo storage isn't connected."""
    from config import ON_VERCEL
    from ...db import using_postgres
    if not ON_VERCEL:
        return []
    out = []
    if not using_postgres():
        out.append("The database isn't connected (DATABASE_URL from Neon), so changes are lost when Vercel restarts the site.")
    if current_app.config.get("MEDIA_STORAGE") != "blob":
        out.append("Photo storage isn't connected (Vercel Blob), so uploaded photos are lost when Vercel restarts the site. "
                   "This deployment doesn't see BLOB_STORE_ID: connect a Blob store to this project, then redeploy.")
    return out


# ======================================================================
#  Products
# ======================================================================
@bp.route("/products")
@login_required
def products_list():
    q = request.args.get("q", "").strip()
    cat = request.args.get("category") or None
    items = products.list_products(active_only=False, search=q or None, category=cat if cat in products.CATEGORIES else None)
    return render_template("admin/products.html", items=items, q=q, cat=cat, cats=products.CATEGORIES,
                           today=date.today().isoformat())


@bp.route("/products/new", methods=["GET", "POST"])
@login_required
def product_new():
    if request.method == "POST":
        try:
            data = product_from_form(request.form)
        except FormError as e:
            flash(str(e), "error")
            return render_template("admin/product_form.html", product=None, form=request.form, cats=products.CATEGORIES)
        pid = products.create(data)
        saved, errors = _save_photos(request.files.getlist("photos"), "products", cutout=bool(request.form.get("cutout")))
        for name in saved:
            products.add_image(pid, name)
        for e in errors:
            flash(e, "error")
        flash(f"“{data['name']}” added.", "success")
        return redirect(_back(_edit_url(pid)))
    return render_template("admin/product_form.html", product=None,
                           form={"is_active": 1, "in_stock": 1, "stock_qty": 1, "discount_percent": 0}, cats=products.CATEGORIES)


def _edit_url(product_id, anchor=""):
    item = products.get(product_id, active_only=False) or abort(404)
    return url_for("admin.product_edit", slug=item["slug"]) + anchor


@bp.route("/products/<slug>", methods=["GET", "POST"])
@login_required
def product_edit(slug):
    item = products.get_by_slug(slug, active_only=False) or abort(404)
    product_id = item["id"]
    if request.method == "POST":
        try:
            data = product_from_form(request.form)
        except FormError as e:
            flash(str(e), "error")
            return render_template("admin/product_form.html", product=item, form=request.form, cats=products.CATEGORIES)
        products.update(product_id, data)
        saved, errors = _save_photos(request.files.getlist("photos"), "products", cutout=bool(request.form.get("cutout")))
        for name in saved:
            products.add_image(product_id, name)
        for e in errors:
            flash(e, "error")
        flash("Changes saved.", "success")
        return redirect(_edit_url(product_id))
    form = dict(item)
    form["price"] = currency.plain(item["price_cents"] / 100, settings.currency_code())
    form["on_home"] = item["home_position"] > 0
    return render_template("admin/product_form.html", product=item, form=form, cats=products.CATEGORIES)


@bp.route("/products/<int:product_id>/toggle", methods=["POST"])
@login_required
def product_toggle(product_id):
    item = products.get(product_id, active_only=False) or abort(404)
    products.set_active(product_id, not item["is_active"])
    flash(f"“{item['short']}” is now {'hidden' if item['is_active'] else 'visible'} in the shop.", "success")
    return redirect(request.form.get("back") or url_for("admin.products_list"))


@bp.route("/products/<int:product_id>/delete", methods=["POST"])
@login_required
def product_delete(product_id):
    item = products.get(product_id, active_only=False) or abort(404)
    products.delete(product_id)
    flash(f"“{item['short']}” deleted.", "success")
    return redirect(url_for("admin.products_list"))


@bp.route("/products/<int:product_id>/photos/<int:image_id>/<action>", methods=["POST"])
@login_required
def product_photo(product_id, image_id, action):
    if action == "delete":
        products.delete_image(product_id, image_id)
        flash("Photo removed.", "success")
    elif action == "cover":
        products.make_cover(product_id, image_id)
        flash("Main photo updated.", "success")
    else:
        abort(404)
    return redirect(_edit_url(product_id, "#photos"))


# ======================================================================
#  Studio services
# ======================================================================
@bp.route("/services")
@login_required
def services_list():
    return render_template("admin/services.html", items=services.list_services(active_only=False),
                           gear_items=gear.list_gear(active_only=False))


# ---------- Studio gear (equipment the studio uses — not for sale) ----------
def _gear_from_form(f):
    name = f.get("name", "").strip()
    if not name:
        raise FormError("Give the gear a name.")
    try:
        pos = int(f.get("position") or 0)
    except ValueError:
        raise FormError("Order must be a whole number.")
    return {"name": name[:120], "role": f.get("role", "").strip()[:40], "description": f.get("description", "").strip()[:600],
            "is_active": 1 if f.get("is_active") else 0, "position": pos}


@bp.route("/services/gear/new", methods=["GET", "POST"])
@bp.route("/services/gear/<slug>", methods=["GET", "POST"])
@login_required
def service_gear_edit(slug=None):
    item = gear.get_by_slug(slug) if slug else None
    if slug and not item:
        abort(404)
    if request.method == "POST":
        try:
            data = _gear_from_form(request.form)
        except FormError as e:
            flash(str(e), "error")
            return render_template("admin/gear_form.html", item=item, form=request.form)
        saved, errors = _save_photos(request.files.getlist("photo")[:1], "gear", cutout=bool(request.form.get("cutout")))
        for e in errors:
            flash(e, "error")
        if item:
            new_slug = gear.update(item["id"], data, saved[0] if saved else None)
        else:
            new_slug = gear.create(data, saved[0] if saved else "")
        flash("Gear saved.", "success")
        return redirect(_back(url_for("admin.service_gear_edit", slug=new_slug)))
    form = dict(item) if item else {"is_active": 1, "position": len(gear.list_gear(False)) + 1}
    return render_template("admin/gear_form.html", item=item, form=form)


@bp.route("/services/gear/<slug>/delete", methods=["POST"])
@login_required
def service_gear_delete(slug):
    item = gear.get_by_slug(slug) or abort(404)
    gear.delete(item["id"])
    flash(f"“{item['name']}” removed from studio gear.", "success")
    return redirect(url_for("admin.services_list") + "#gear")


@bp.route("/services/new", methods=["GET", "POST"])
@bp.route("/services/<slug>", methods=["GET", "POST"])
@login_required
def service_edit(slug=None):
    item = services.get_by_slug(slug) if slug else None
    if slug and not item:
        abort(404)
    service_id = item["id"] if item else None
    if request.method == "POST":
        try:
            data = service_from_form(request.form, services.ICONS)
        except FormError as e:
            flash(str(e), "error")
            return render_template("admin/service_form.html", service=item, form=request.form, icons=services.ICONS)
        if item:
            services.update(service_id, data)
        else:
            service_id = services.create(data)
        saved, errors = _save_photos(request.files.getlist("photos"), "services")
        for name in saved:
            services.add_image(service_id, name, data["name"])
        for e in errors:
            flash(e, "error")
        flash("Service saved.", "success")
        return redirect(_back(url_for("admin.service_edit", slug=services.get(service_id)["slug"])))
    form = dict(item) if item else {"is_active": 1, "position": len(services.list_services(False)) + 1}
    if item and item["price_cents"] is not None:
        form["price_amount"] = currency.plain(item["price_cents"] / 100, settings.currency_code())
    return render_template("admin/service_form.html", service=item, form=form, icons=services.ICONS)


@bp.route("/services/<int:service_id>/delete", methods=["POST"])
@login_required
def service_delete(service_id):
    services.delete(service_id)
    flash("Service deleted.", "success")
    return redirect(url_for("admin.services_list"))


@bp.route("/services/<int:service_id>/photos/<int:image_id>/<action>", methods=["POST"])
@login_required
def service_photo(service_id, image_id, action):
    if action == "delete":
        services.delete_image(service_id, image_id)
    elif action == "cover":
        services.make_cover(service_id, image_id)
    else:
        abort(404)
    flash("Photos updated.", "success")
    return redirect(url_for("admin.service_edit", slug=services.get(service_id)["slug"]) + "#photos")


# ======================================================================
#  Portfolio
# ======================================================================
@bp.route("/portfolio", methods=["GET", "POST"])
@login_required
def portfolio_admin():
    if request.method == "POST":
        saved, errors = _save_photos(request.files.getlist("photos"), "portfolio")
        category = request.form.get("category") if request.form.get("category") in portfolio.CATEGORIES else "Portrait"
        for name in saved:
            portfolio.add(name, request.form.get("title", "").strip()[:120], category, request.form.get("instagram", ""))
        for e in errors:
            flash(e, "error")
        if saved:
            flash(f"{len(saved)} photo{'s' if len(saved) > 1 else ''} added to the portfolio.", "success")
        elif not errors:
            flash("Choose at least one photo.", "error")
        return redirect(url_for("admin.portfolio_admin"))
    return render_template("admin/portfolio.html", items=portfolio.list_items(), cats=portfolio.CATEGORIES)


@bp.route("/portfolio/<int:item_id>", methods=["POST"])
@login_required
def portfolio_item(item_id):
    if request.form.get("action") == "delete":
        portfolio.delete(item_id)
        flash("Photo removed from the portfolio.", "success")
    else:
        cat = request.form.get("category") if request.form.get("category") in portfolio.CATEGORIES else "Portrait"
        try:
            pos = int(request.form.get("position") or 0)
        except ValueError:
            pos = 0
        portfolio.update(item_id, request.form.get("title", "").strip()[:120], cat, pos, request.form.get("instagram", ""))
        flash("Saved.", "success")
    return redirect(url_for("admin.portfolio_admin"))


# ======================================================================
#  Store settings
# ======================================================================
@bp.route("/settings", methods=["GET", "POST"])
@login_required
def settings_page():
    if request.method == "POST":
        data = request.form.to_dict()
        data.pop("giveaway_until", None)   # only the Giveaway page changes this
        settings.save(data)
        flash("Store details saved.", "success")
        return redirect(url_for("admin.settings_page"))
    return render_template("admin/settings.html", s=settings.all_settings(), social=settings.SOCIAL,
                           currency_choices=currency.choices())


# ======================================================================
#  Inbox
# ======================================================================
@bp.route("/inbox")
@login_required
def inbox_page():
    data = dict(bookings=inbox.bookings(), messages=inbox.messages(),
                services={s["slug"]: s["name"] for s in services.list_services(False)})
    inbox.mark_all_read()
    return render_template("admin/inbox.html", **data)


@bp.route("/inbox/<kind>/<int:item_id>/delete", methods=["POST"])
@login_required
def inbox_delete(kind, item_id):
    if kind not in ("booking", "message"):
        abort(404)
    inbox.delete(kind, item_id)
    flash("Deleted.", "success")
    return redirect(url_for("admin.inbox_page"))


# ======================================================================
#  Account & team
# ======================================================================
@bp.route("/account", methods=["GET", "POST"])
@login_required
def account():
    if request.method == "POST":
        action = request.form.get("action")
        if action == "password":
            if not users.check_password(g.user["id"], request.form.get("current")):
                flash("Your current password isn't right.", "error")
            else:
                error = users.validate_password(request.form.get("password"), request.form.get("confirm"))
                if error:
                    flash(error, "error")
                else:
                    users.set_password(g.user["id"], request.form["password"])
                    flash("Password changed.", "success")
        elif action == "add_user":
            email, name = request.form.get("email", "").strip(), request.form.get("name", "").strip()
            error = None if (email and "@" in email and name) else "Enter a name and a valid email."
            error = error or users.validate_password(request.form.get("password"))
            if not error:
                try:
                    users.create(email, name, request.form["password"])
                    flash(f"{name} can now sign in.", "success")
                except Exception:
                    error = "An account with that email already exists."
            if error:
                flash(error, "error")
        elif action == "remove_user":
            uid = int(request.form.get("user_id", 0))
            if uid == g.user["id"]:
                flash("You can't remove your own account.", "error")
            else:
                users.delete(uid)
                flash("Account removed.", "success")
        return redirect(url_for("admin.account"))
    return render_template("admin/account.html", team=users.all_users())



# ======================================================================
#  Giveaway
# ======================================================================
@bp.route("/giveaway", methods=["GET", "POST"])
@login_required
def giveaway():
    if request.method == "POST":          # "Start the giveaway now"
        from .forms import parse_price
        kind = request.form.get("prize_kind", "device")
        try:
            prizes = max(1, min(giveaways.MAX_PRIZES, int(request.form.get("prizes", "1"))))
            minutes = int(request.form.get("minutes", "60"))
            product_id = int(request.form.get("product_id") or 0) or None
            amount = parse_price(request.form.get("amount"), required=False) if kind == "money" else None
            prize, product_id, amount = giveaways.prize_for(kind, product_id, amount)
            if minutes not in dict(giveaways.DURATIONS):
                raise ValueError("Choose how long the giveaway runs.")
            giveaways.start(prize, prizes, minutes, g.user["id"], kind, product_id, amount)
            flash(f"Giveaway started: {prizes} × {prize}. Winners will be picked at random moments.", "success")
        except (ValueError, FormError) as exc:
            flash(str(exc), "error")
        return redirect(url_for("admin.giveaway"))

    code = request.args.get("code", "").strip()
    checked = None
    if code:
        win = giveaways.find(code)
        checked = giveaways.describe(win) if win else {"status": "unknown", "code": code}
    test_token = request.args.get("test", "")
    test_link = (url_for("main.giveaway_try", token=test_token, _external=True)
                 if giveaways.test_giveaway(test_token) else None)
    return render_template("admin/giveaway.html", live=giveaways.running(), history=giveaways.history(),
                           test_link=test_link, test_minutes=giveaways.TEST_MINUTES,
                           devices=products.list_products(), categories=products.CATEGORIES,
                           durations=giveaways.DURATIONS, max_prizes=giveaways.MAX_PRIZES,
                           checked=checked, claim_days=giveaways.CLAIM_DAYS)


@bp.route("/giveaway/test", methods=["POST"])
@login_required
def giveaway_test():
    token = giveaways.start_test(g.user["id"])
    return redirect(url_for("admin.giveaway", test=token) + "#try")


@bp.route("/giveaway/stop", methods=["POST"])
@login_required
def giveaway_stop():
    giveaways.stop()
    flash("Giveaway stopped. Prizes already won can still be collected.", "success")
    return redirect(url_for("admin.giveaway"))


@bp.route("/giveaway/collect", methods=["POST"])
@login_required
def giveaway_collect():
    code = request.form.get("code", "")
    name = request.form.get("name", "").strip()[:80]
    phone = request.form.get("phone", "").strip()[:40]
    if not name:
        flash("Write the winner's name before handing over the prize.", "error")
    else:
        try:
            giveaways.mark_collected(code, name, phone, g.user["id"])
            flash(f"Prize handed over to {name}. The code can't be used again.", "success")
        except ValueError as exc:
            flash(str(exc), "error")
    return redirect(url_for("admin.giveaway", code=giveaways.normalise_code(code) or code))
