"""
Photography (/admin/photography): what the public Photography page shows, in three tabs.

    Gear        name, price in Canadian dollars, photos
    Services    the studio's services (name, "from" price, duration, icon, photo, description)
    Portfolio   photos, each with the Instagram account of the person in it
Each tab has + Add, and every item can be removed (gear and services can also be edited).
"""
import re

from flask import abort, flash, redirect, render_template, request, url_for

from .admin import FormError, amount, audit, bp, login_required, text
from .extensions import db
from .models import GearItem, PortfolioItem, Service

TABS = {"gear": "Gear", "services": "Services", "portfolio": "Portfolio"}
SERVICE_ICONS = {"camera": "Camera", "user": "Portrait", "users": "Group", "heart": "Wedding", "graduation": "Graduation",
                 "video": "Video", "package": "Product", "aperture": "Lens", "image": "Print"}
MODELS = {"gear": GearItem, "services": Service, "portfolio": PortfolioItem}


@bp.route("/photography")
@login_required
def photography():
    tab = request.args.get("tab", "gear")
    tab = tab if tab in TABS else "gear"
    rows = {key: model.query.order_by(model.position, model.id).all() for key, model in MODELS.items()}
    return render_template("admin/photography.html", tab=tab, tabs=TABS, rows=rows, service_icons=SERVICE_ICONS)


# ---------------------------------------------------------------- reading the forms
def _photo(value, label="Photo"):
    value = (value or "").strip()
    if not (value.startswith("https://") or value.startswith("/static/")):
        raise FormError(f"{label}: paste the full link, starting with https://")
    return value[:500]


def _gear(f):
    photos = [_photo(line, "Photos") for line in (f.get("photos") or "").splitlines() if line.strip()]
    if not photos:
        raise FormError("Add at least one photo link.")
    return {"name": text(f, "name", "the name", limit=120), "price_cad": amount(f.get("price"), "Price (CAD)"),
            "photo_links": "\n".join(photos)}


def _service(f):
    icon = f.get("icon", "")
    if icon not in SERVICE_ICONS:
        raise FormError("Choose an icon.")
    return {"name": text(f, "name", "the service name", limit=80), "price_from": amount(f.get("price"), "Price from"),
            "duration": text(f, "duration", "how long it takes", limit=40), "icon": icon,
            "photo": _photo(f.get("photo")), "description": text(f, "description", "a short description", limit=600)}


def instagram_link(value):
    """"@aline.rw", "aline.rw" or a full link → https://www.instagram.com/aline.rw/"""
    value = (value or "").strip()
    if "instagram.com/" in value:
        value = value.split("instagram.com/", 1)[1]
    handle = value.lstrip("@").strip("/").split("/")[0].split("?")[0]
    if not re.fullmatch(r"[A-Za-z0-9._]{1,30}", handle):
        raise FormError("Instagram: the person's account, like @aline.rw")
    return f"https://www.instagram.com/{handle}/"


def _portfolio(f):
    return {"photo": _photo(f.get("photo")), "instagram": instagram_link(f.get("instagram"))}


READERS = {"gear": _gear, "services": _service, "portfolio": _portfolio}
NAMES = {"gear": "Gear", "services": "Service", "portfolio": "Photo"}


def _back(tab):
    return redirect(url_for("admin.photography", tab=tab))


def _label(kind, row):
    return getattr(row, "name", "") or getattr(row, "handle", "") or "Photo"


# ---------------------------------------------------------------- add, edit, remove
@bp.route("/photography/<kind>/add", methods=["POST"])
@login_required
def photography_add(kind):
    if kind not in MODELS:
        abort(404)
    model = MODELS[kind]
    try:
        data = READERS[kind](request.form)
        last = db.session.query(db.func.max(model.position)).scalar()
        row = model(position=(last or 0) + 1, is_active=True, **data)
        db.session.add(row)
        db.session.flush()
        audit(f"photography.{kind}.add", f"#{row.id} {_label(kind, row)}")
        db.session.commit()
        flash(f"{NAMES[kind]} added. It shows on the Photography page now.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return _back(kind)


@bp.route("/photography/<kind>/<int:row_id>/edit", methods=["POST"])
@login_required
def photography_edit(kind, row_id):
    if kind not in ("gear", "services"):
        abort(404)
    row = db.session.get(MODELS[kind], row_id) or abort(404)
    try:
        for key, value in READERS[kind](request.form).items():
            setattr(row, key, value)
        audit(f"photography.{kind}.edit", f"#{row.id} {_label(kind, row)}")
        db.session.commit()
        flash(f"{_label(kind, row)} saved.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return _back(kind)


@bp.route("/photography/<kind>/<int:row_id>/remove", methods=["POST"])
@login_required
def photography_remove(kind, row_id):
    if kind not in MODELS:
        abort(404)
    row = db.session.get(MODELS[kind], row_id) or abort(404)
    label = _label(kind, row)
    db.session.delete(row)
    audit(f"photography.{kind}.remove", f"#{row_id} {label}")
    db.session.commit()
    flash(f"{label} removed from the Photography page.", "success")
    return _back(kind)
