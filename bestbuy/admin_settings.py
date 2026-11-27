"""
Settings (/admin/settings): the store details the website shows, in four groups, each with its own pop-up:
    Contact        phone, WhatsApp, email
    Address        address and a Google Maps link
    Working hours  opening and closing times: Monday to Friday, Saturday, Sunday
    Social         Instagram, Facebook, TikTok (can be added later)
"""
import re

from flask import flash, g, redirect, render_template, request, url_for

from .admin import FormError, audit, bp, login_required, text
from .extensions import db
from .models import Setting

DAYS = (("hours_week", "Monday to Friday"), ("hours_sat", "Saturday"), ("hours_sun", "Sunday"))


def save(values):
    g.pop("store", None)                      # read the new values on the next page
    for key, value in values.items():
        row = db.session.get(Setting, key)
        if row:
            row.value = value
        else:
            db.session.add(Setting(key=key, value=value))


def _link(f, name, label, required):
    value = (f.get(name) or "").strip()
    if not value and not required:
        return ""
    if not value.startswith("https://"):
        raise FormError(f"{label}: paste the full link, starting with https://")
    return value[:300]


def _contact(f):
    phone = text(f, "phone", "the phone number", limit=40)
    whatsapp = re.sub(r"\D", "", f.get("whatsapp") or "")
    if len(whatsapp) < 9:
        raise FormError("WhatsApp: the number with its country code, e.g. 250788123456.")
    email = (f.get("email") or "").strip().lower()
    if not re.fullmatch(r"[^@\s]+@[^@\s]+\.[^@\s]+", email):
        raise FormError("Enter a valid email address.")
    return {"phone": phone, "whatsapp": whatsapp, "email": email}


def _address(f):
    return {"address": text(f, "address", "the address", limit=200),
            "map_url": _link(f, "map_url", "Google Maps link", required=False)}


def _hours(f):
    values = {}
    for key, label in DAYS:
        if f.get(f"{key}_closed"):
            values[key] = ""
            continue
        opens, closes = f.get(f"{key}_open", ""), f.get(f"{key}_close", "")
        if not (re.fullmatch(r"\d\d:\d\d", opens) and re.fullmatch(r"\d\d:\d\d", closes)):
            raise FormError(f"{label}: choose the opening and closing times, or tick Closed.")
        if closes <= opens:
            raise FormError(f"{label}: closing time must be after opening time.")
        values[key] = f"{opens}-{closes}"
    return values


def _social(f):
    return {key: _link(f, key, label, required=False)
            for key, label in (("instagram", "Instagram"), ("facebook", "Facebook"), ("tiktok", "TikTok"))}


SECTIONS = {"contact": ("Contact", _contact), "address": ("Address", _address),
            "hours": ("Working hours", _hours), "social": ("Social", _social)}


@bp.route("/settings")
@login_required
def settings():
    hours = {key: Setting.store().get(key, "") for key, _ in DAYS}
    return render_template("admin/settings.html", days=DAYS, hours=hours)


@bp.route("/settings/<section>", methods=["POST"])
@login_required
def settings_save(section):
    if section not in SECTIONS:
        return redirect(url_for("admin.settings"))
    label, read = SECTIONS[section]
    try:
        values = read(request.form)
        save(values)
        audit("settings." + section, ", ".join(f"{k}={v}" for k, v in values.items()))
        db.session.commit()
        flash(f"{label} saved. The website shows it now.", "success")
    except FormError as e:
        db.session.rollback()
        flash(str(e), "error")
    return redirect(url_for("admin.settings"))
