"""Products, their photos, prices and discounts."""
import re
from datetime import date

from ..db import execute, get_db, query
from .. import images

# slug -> (label, icon)
CATEGORIES = {
    "cameras": ("Cameras", "camera"),
    "lenses": ("Lenses", "aperture"),
    "audio": ("Audio", "headphones"),
    "computers": ("Computers", "laptop"),
    "phones": ("Phones & Tablets", "smartphone"),
    "accessories": ("Accessories", "plug"),
}

EDITABLE = ("slug", "name", "short_name", "category", "description", "tagline", "price_cents", "discount_percent",
            "discount_ends", "badge", "icon", "studio_gear", "gear_role", "home_position", "in_stock",
            "is_active", "position")


def slugify(text):
    """'Canon RF 50mm f/1.8' -> 'canon-rf-50mm-f-1-8' (used in the product page address)."""
    text = (text or "").lower().replace("″", "").replace('"', "").replace("°", "")
    slug = re.sub(r"[^a-z0-9]+", "-", text).strip("-")[:80].strip("-") or "product"
    return slug + "-item" if slug.isdigit() else slug   # a number-only address would look like an old link


def unique_slug(name, exclude_id=None):
    base = slugify(name)
    slug, n = base, 2
    while query("SELECT 1 FROM products WHERE slug = ? AND id IS NOT ?", (slug, exclude_id), one=True):
        slug, n = f"{base}-{n}", n + 1
    return slug


def discount_active(row, today=None):
    if not row["discount_percent"]:
        return False
    ends = row["discount_ends"]
    return not ends or ends >= (today or date.today()).isoformat()


def _decorate(row, imgs):
    """Turn a database row into what templates need (prices in dollars, photo URLs …)."""
    p = dict(row)
    on_sale = discount_active(row)
    final_cents = round(row["price_cents"] * (100 - row["discount_percent"]) / 100) if on_sale else row["price_cents"]
    p.update(
        short=row["short_name"] or row["name"],
        price=final_cents / 100,
        original_price=row["price_cents"] / 100,
        price_cents_final=final_cents,
        on_sale=on_sale,
        save_amount=(row["price_cents"] - final_cents) / 100,
        category_label=CATEGORIES.get(row["category"], (row["category"].title(), ""))[0],
        images=[dict(i) for i in imgs],
        gallery=[images.media_url(i["filename"]) for i in imgs],
        image_url=images.media_url(imgs[0]["filename"]) if imgs else None,
        role=row["gear_role"],
    )
    p["image"] = p["image_url"]
    return p


def _with_images(rows):
    if not rows:
        return []
    ids = [r["id"] for r in rows]
    marks = ",".join("?" * len(ids))
    imgs = query(f"SELECT * FROM product_images WHERE product_id IN ({marks}) ORDER BY position, id", ids)
    by_product = {}
    for i in imgs:
        by_product.setdefault(i["product_id"], []).append(i)
    return [_decorate(r, by_product.get(r["id"], [])) for r in rows]


def list_products(active_only=True, category=None, search=None, sort=None, studio_gear=None, on_home=False, on_sale=None):
    sql, args = ["SELECT * FROM products WHERE 1=1"], []
    if active_only:
        sql.append("AND is_active = 1")
    if category:
        sql.append("AND category = ?"); args.append(category)
    if search:
        sql.append("AND (name LIKE ? OR description LIKE ?)"); args += [f"%{search}%"] * 2
    if studio_gear is not None:
        sql.append("AND studio_gear = ?"); args.append(1 if studio_gear else 0)
    if on_home:
        sql.append("AND home_position > 0")
    order = {"price_asc": "price_cents ASC", "price_desc": "price_cents DESC", "newest": "id DESC"}.get(sort)
    if search and not order and not on_home:
        # best matches first: the exact name, then names containing it, then descriptions
        order = "(LOWER(name) = LOWER(?)) DESC, (name LIKE ?) DESC, position, id"
        args += [search, f"%{search}%"]
    sql.append("ORDER BY " + ("home_position, id" if on_home else order or "position, id"))
    items = _with_images(query(" ".join(sql), args))
    if on_sale is not None:
        items = [p for p in items if p["on_sale"] == on_sale]
    if sort in ("price_asc", "price_desc"):  # sort by price after discount
        items.sort(key=lambda p: p["price"], reverse=sort == "price_desc")
    return items


def get_by_slug(slug, active_only=True):
    row = query("SELECT * FROM products WHERE slug = ?" + (" AND is_active = 1" if active_only else ""), (slug,), one=True)
    return _with_images([row])[0] if row else None


def get(product_id, active_only=True):
    row = query("SELECT * FROM products WHERE id = ?" + (" AND is_active = 1" if active_only else ""), (product_id,), one=True)
    return _with_images([row])[0] if row else None


def related(product, limit=3):
    rows = query("SELECT * FROM products WHERE category = ? AND id != ? AND is_active = 1 ORDER BY position, id LIMIT ?",
                 (product["category"], product["id"], limit))
    return _with_images(rows)


def counts():
    r = query("""SELECT COUNT(*) AS total, SUM(is_active) AS active, SUM(CASE WHEN in_stock = 0 THEN 1 ELSE 0 END) AS sold_out
                 FROM products""", one=True)
    sale = len(list_products(active_only=True, on_sale=True))
    return {"total": r["total"] or 0, "active": r["active"] or 0, "sold_out": r["sold_out"] or 0, "on_sale": sale}


def create(data):
    data = {k: data[k] for k in EDITABLE if k in data}
    data["slug"] = unique_slug(data["name"])
    if "position" not in data:
        data["position"] = (query("SELECT COALESCE(MAX(position), 0) + 1 AS n FROM products", one=True)["n"])
    cols = ", ".join(data)
    return execute(f"INSERT INTO products ({cols}) VALUES ({', '.join('?' * len(data))})", tuple(data.values()))


def update(product_id, data):
    data = {k: data[k] for k in EDITABLE if k in data}
    old = query("SELECT name FROM products WHERE id = ?", (product_id,), one=True)
    if old and "name" in data and data["name"] != old["name"]:
        data["slug"] = unique_slug(data["name"], exclude_id=product_id)   # address follows the new name
    sets = ", ".join(f"{k} = ?" for k in data)
    execute(f"UPDATE products SET {sets}, updated_at = datetime('now') WHERE id = ?", (*data.values(), product_id))


def set_active(product_id, active):
    execute("UPDATE products SET is_active = ?, updated_at = datetime('now') WHERE id = ?", (1 if active else 0, product_id))


def delete(product_id):
    for img in query("SELECT filename FROM product_images WHERE product_id = ?", (product_id,)):
        images.delete_file(img["filename"])
    execute("DELETE FROM products WHERE id = ?", (product_id,))


# ---------- photos ----------
def add_image(product_id, filename):
    pos = query("SELECT COALESCE(MAX(position), -1) + 1 AS n FROM product_images WHERE product_id = ?", (product_id,), one=True)["n"]
    return execute("INSERT INTO product_images (product_id, filename, position) VALUES (?, ?, ?)", (product_id, filename, pos))


def delete_image(product_id, image_id):
    row = query("SELECT * FROM product_images WHERE id = ? AND product_id = ?", (image_id, product_id), one=True)
    if row:
        images.delete_file(row["filename"])
        execute("DELETE FROM product_images WHERE id = ?", (image_id,))
        _renumber(product_id)


def make_cover(product_id, image_id):
    """Move a photo to the front — it becomes the main picture everywhere."""
    db = get_db()
    db.execute("UPDATE product_images SET position = position + 1 WHERE product_id = ?", (product_id,))
    db.execute("UPDATE product_images SET position = 0 WHERE id = ? AND product_id = ?", (image_id, product_id))
    db.commit()
    _renumber(product_id)


def _renumber(product_id):
    db = get_db()
    rows = db.execute("SELECT id FROM product_images WHERE product_id = ? ORDER BY position, id", (product_id,)).fetchall()
    for n, r in enumerate(rows):
        db.execute("UPDATE product_images SET position = ? WHERE id = ?", (n, r["id"]))
    db.commit()
