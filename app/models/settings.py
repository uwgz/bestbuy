"""Store details the owner can change from the admin panel (phone, hours, social links …)."""
import re

from flask import g, has_app_context

from .. import currency as currencies
from ..db import get_db, query

DEFAULTS = {
    "name": "Vision Electronics",
    "tagline": "See more. Capture everything.",
    "phone": "",
    "email": "",
    "address": "",
    "hours": "",
    "ribbon": "Try any camera or lens in store before you buy.",
    "hero_title": "See more.\nCapture everything.",
    "hero_subtitle": "Cameras, computers and audio from brands you trust — and a photo studio next door.",
    "footer_note": "Free in-store pickup on every order. Photography sessions are confirmed by phone or email within 24 hours.",
    "instagram": "",
    "facebook": "",
    "tiktok": "",
    "youtube": "",
    "x": "",
    "whatsapp": "",
    "whatsapp_orders": "",   # number that receives cart orders (country code + number, digits only)
    "currency": currencies.DEFAULT,     # one ISO code for the whole site (prices are shown in it, not converted)
    "giveaway_until": "",               # end time (UTC) of the giveaway running now — set from the Giveaway page
}

SOCIAL = [("instagram", "Instagram"), ("facebook", "Facebook"), ("tiktok", "TikTok"),
          ("youtube", "YouTube"), ("x", "X"), ("whatsapp", "WhatsApp")]
ICON_FOR = {"x": "x-social"}


def all_settings():
    data = dict(DEFAULTS)
    data.update({r["key"]: r["value"] for r in query("SELECT key, value FROM settings")})
    return data


def save(values):
    db = get_db()
    for key, value in values.items():
        if key in DEFAULTS:
            if key == "currency":
                value = currencies.info(value)[0]
            db.execute("INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                       (key, (value or "").strip()))
    db.commit()
    g.pop("business", None)   # read fresh on the next call


def whatsapp_link(text):
    """wa.me link to the store's WhatsApp with the message already typed in (None if no number set)."""
    from urllib.parse import quote
    number = business()["whatsapp_number"]
    return f"https://wa.me/{number}?text={quote(text)}" if number else None


def business():
    """Settings shaped for templates — read once per request."""
    if has_app_context() and "business" in g:
        return g.business
    s = all_settings()
    s["hours_list"] = [tuple(p.strip() for p in (line.split("|", 1) + [""])[:2])
                       for line in s["hours"].splitlines() if line.strip()]
    s["social_links"] = [(ICON_FOR.get(k, k), label, s[k]) for k, label in SOCIAL if s.get(k)]
    s["hero_title_lines"] = [l for l in s["hero_title"].splitlines() if l.strip()]
    # digits only; falls back to the number in the WhatsApp social link
    s["whatsapp_number"] = re.sub(r"\D", "", s.get("whatsapp_orders") or "") or re.sub(r"\D", "", s.get("whatsapp") or "")
    code, name, symbol, decimals = currencies.info(s.get("currency"))
    s.update(currency=code, currency_name=name, currency_symbol=symbol, currency_decimals=decimals)
    if has_app_context():
        g.business = s
    return s


def currency_code():
    return business()["currency"]
