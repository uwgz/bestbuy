"""Reading and checking admin form input."""
import re
from datetime import date, timedelta

from ...models.products import CATEGORIES, NAME_WORDS, SHORT_WORDS, auto_short, words


class FormError(ValueError):
    pass


MAX_PRICE = 100_000_000_000   # in the store's currency (big enough for RWF, UGX, IDR …)


def parse_price(text, required=True):
    """'1,299.99', '$1299' or 'RWF 12 000' -> 129999 / 1200000 (hundredths). Empty -> None if not required."""
    cleaned = re.sub(r"[^\d.]", "", text or "")
    if not cleaned:
        if required:
            raise FormError("Enter a price, for example 1299.99")
        return None
    if cleaned.count(".") > 1 or cleaned == ".":
        raise FormError("Enter a price, for example 1299.99")
    cents = round(float(cleaned) * 100)
    if cents <= 0 or cents > MAX_PRICE * 100:
        raise FormError(f"Enter a price above 0 and up to {MAX_PRICE:,}.")
    return cents


def parse_int(text, low, high, label):
    try:
        value = int((text or "0").strip() or 0)
    except ValueError:
        raise FormError(f"{label} must be a whole number.")
    if not low <= value <= high:
        raise FormError(f"{label} must be between {low} and {high}.")
    return value


def parse_date(text):
    text = (text or "").strip()
    if not text:
        return None
    try:
        return date.fromisoformat(text).isoformat()
    except ValueError:
        raise FormError("Use a valid date for the discount end.")


def product_from_form(f):
    name = " ".join(f.get("name", "").split())
    if not name:
        raise FormError("Give the product a name.")
    if len(words(name)) > NAME_WORDS:
        raise FormError(f"Keep the product name to {NAME_WORDS} words or fewer.")
    short = " ".join(f.get("short_name", "").split()) or auto_short(name)
    if len(words(short)) > SHORT_WORDS or len(short) > 32:
        raise FormError(f"Keep the short name to {SHORT_WORDS} words (32 letters) or fewer.")
    category = f.get("category")
    if category not in CATEGORIES:
        raise FormError("Choose a category.")
    return {
        "name": name[:200],
        "short_name": short,
        "category": category,
        "description": f.get("description", "").strip()[:4000],
        "tagline": f.get("tagline", "").strip()[:200],
        "price_cents": parse_price(f.get("price")),
        "discount_percent": parse_int(f.get("discount_percent"), 0, 90, "Discount"),
        "discount_ends": parse_date(f.get("discount_ends")),
        "badge": f.get("badge", "").strip()[:30],
        "icon": CATEGORIES[category][1],
        "home_position": parse_int(f.get("home_position"), 0, 99, "Home page position") if f.get("on_home") else 0,
        "stock_qty": (qty := parse_int(f.get("stock_qty"), 0, 100000, "Units in stock")),
        "in_stock": 1 if qty > 0 else 0,
        "is_active": 1 if f.get("is_active") else 0,
    }


def service_from_form(f, icons):
    name = f.get("name", "").strip()
    if not name:
        raise FormError("Give the service a name.")
    icon = f.get("icon") if f.get("icon") in icons else icons[0]
    return {
        "name": name[:80],
        "icon": icon,
        "tagline": f.get("tagline", "").strip()[:160],
        "description": f.get("description", "").strip()[:2000],
        "includes": "\n".join(l.strip() for l in f.get("includes", "").splitlines() if l.strip())[:1000],
        "price_prefix": f.get("price_prefix", "").strip()[:30],
        "price_cents": parse_price(f.get("price_amount"), required=False),
        "price_suffix": f.get("price_suffix", "").strip()[:30],
        "is_active": 1 if f.get("is_active") else 0,
        "position": parse_int(f.get("position"), 0, 999, "Order"),
    }


def sale_from_form(f):
    try:
        product_id = int(f.get("product_id") or 0)
    except ValueError:
        product_id = 0
    if not product_id:
        raise FormError("Choose the product you sold.")
    qty = parse_int(f.get("qty"), 1, 10000, "Quantity")
    unit = parse_price(f.get("unit_price"))
    try:
        sold_on = date.fromisoformat((f.get("sold_on") or "").strip())
    except ValueError:
        raise FormError("Use a valid date for the sale.")
    if sold_on > date.today() + timedelta(days=1):   # a day of slack: the server runs on UTC
        raise FormError("The sale date can't be in the future.")
    return {"product_id": product_id, "qty": qty, "unit_cents": unit, "sold_on": sold_on.isoformat(),
            "note": (f.get("note") or "").strip()[:200]}
