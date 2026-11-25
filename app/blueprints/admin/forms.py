"""Reading and checking admin form input."""
import re
from datetime import date

from ...models.products import CATEGORIES


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
    name = f.get("name", "").strip()
    if not name:
        raise FormError("Give the product a name.")
    category = f.get("category")
    if category not in CATEGORIES:
        raise FormError("Choose a category.")
    return {
        "name": name[:200],
        "short_name": f.get("short_name", "").strip()[:80],
        "category": category,
        "description": f.get("description", "").strip()[:4000],
        "tagline": f.get("tagline", "").strip()[:200],
        "price_cents": parse_price(f.get("price")),
        "discount_percent": parse_int(f.get("discount_percent"), 0, 90, "Discount"),
        "discount_ends": parse_date(f.get("discount_ends")),
        "badge": f.get("badge", "").strip()[:30],
        "icon": CATEGORIES[category][1],
        "home_position": parse_int(f.get("home_position"), 0, 99, "Home page position") if f.get("on_home") else 0,
        "in_stock": 1 if f.get("in_stock") else 0,
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
