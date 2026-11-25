"""Template helpers available on every page."""
from datetime import datetime, timezone

from flask import session

from . import currency
from .icons import icon
from .models import products, settings


def money(value):
    """Amount in the store's currency: 1299.0 -> '$1,299.00', 12000 -> 'RWF 12,000'."""
    try:
        code = settings.currency_code()
    except Exception:  # database unavailable (error pages)
        code = currency.DEFAULT
    return currency.format_amount(value or 0, code)


def init_app(app):
    app.jinja_env.filters["money"] = money

    @app.context_processor
    def inject():
        cart = session.get("cart", {})
        try:
            business = settings.business()
        except Exception:  # database unavailable → still render pages (e.g. the error page)
            business = dict(settings.DEFAULTS, hours_list=[], social_links=[], hero_title_lines=[], whatsapp_number="",
                            currency_name="", currency_symbol="$", currency_decimals=2)
        try:
            chat = settings.whatsapp_link(f"Hello {business['name']}! I have a question.")
        except Exception:
            chat = None
        return {
            "business": business,
            "whatsapp_chat": chat,     # floating WhatsApp button (hidden when no number is set)
            "categories": {k: v[0] for k, v in products.CATEGORIES.items()},
            "category_icons": {k: v[1] for k, v in products.CATEGORIES.items()},
            "cart_count": sum(cart.values()),
            "year": datetime.now().year,
            # a giveaway is running (no extra database work: the end time is part of the store settings)
            "giveaway_live": bool(business.get("giveaway_until"))
                             and business["giveaway_until"] > datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "icon": icon,
        }
