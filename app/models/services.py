"""Photography services (Portraits, Weddings …) and their photos."""
from ..db import execute, get_db, query
from .. import images
from .products import slugify

EDITABLE = ("name", "icon", "tagline", "description", "includes", "price_prefix", "price_cents", "price_suffix",
            "is_active", "position")
ICONS = ["user", "users", "heart", "package", "printer", "graduation", "camera", "video", "image", "star"]


def _decorate(row, imgs):
    s = dict(row)
    s["includes_list"] = [l.strip() for l in (row["includes"] or "").splitlines() if l.strip()]
    s["images"] = [dict(i) | {"url": images.media_url(i["filename"])} for i in imgs]
    s["price"] = price_text(row)
    return s


def price_text(row):
    """'from RWF 149,000 / session' in the store currency ('' when nothing is set)."""
    from ..helpers import money
    amount = money(row["price_cents"] / 100) if row["price_cents"] is not None else ""
    return " ".join(part for part in (row["price_prefix"], amount, row["price_suffix"]) if part)


def list_services(active_only=True):
    rows = query("SELECT * FROM services" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY position, id")
    imgs = query("SELECT * FROM service_images ORDER BY position, id")
    by = {}
    for i in imgs:
        by.setdefault(i["service_id"], []).append(i)
    return [_decorate(r, by.get(r["id"], [])) for r in rows]


def get(service_id):
    row = query("SELECT * FROM services WHERE id = ?", (service_id,), one=True)
    if not row:
        return None
    return _decorate(row, query("SELECT * FROM service_images WHERE service_id = ? ORDER BY position, id", (service_id,)))


def get_by_slug(slug):
    row = query("SELECT id FROM services WHERE slug = ?", (slug,), one=True)
    return get(row["id"]) if row else None


def create(data):
    data = {k: data[k] for k in EDITABLE if k in data}
    base, slug, n = slugify(data["name"]), slugify(data["name"]), 2
    while query("SELECT 1 FROM services WHERE slug = ?", (slug,), one=True):
        slug, n = f"{base}-{n}", n + 1
    data["slug"] = slug
    data.setdefault("price_prefix", "from")
    data.setdefault("position", query("SELECT COALESCE(MAX(position), 0) + 1 AS n FROM services", one=True)["n"])
    return execute(f"INSERT INTO services ({', '.join(data)}) VALUES ({', '.join('?' * len(data))})", tuple(data.values()))


def update(service_id, data):
    data = {k: data[k] for k in EDITABLE if k in data}
    execute(f"UPDATE services SET {', '.join(f'{k} = ?' for k in data)} WHERE id = ?", (*data.values(), service_id))


def delete(service_id):
    for img in query("SELECT filename FROM service_images WHERE service_id = ?", (service_id,)):
        images.delete_file(img["filename"])
    execute("DELETE FROM services WHERE id = ?", (service_id,))


def add_image(service_id, filename, alt=""):
    pos = query("SELECT COALESCE(MAX(position), -1) + 1 AS n FROM service_images WHERE service_id = ?", (service_id,), one=True)["n"]
    return execute("INSERT INTO service_images (service_id, filename, alt, position) VALUES (?, ?, ?, ?)", (service_id, filename, alt, pos))


def delete_image(service_id, image_id):
    row = query("SELECT * FROM service_images WHERE id = ? AND service_id = ?", (image_id, service_id), one=True)
    if row:
        images.delete_file(row["filename"])
        execute("DELETE FROM service_images WHERE id = ?", (image_id,))


def make_cover(service_id, image_id):
    db = get_db()
    db.execute("UPDATE service_images SET position = position + 1 WHERE service_id = ?", (service_id,))
    db.execute("UPDATE service_images SET position = 0 WHERE id = ? AND service_id = ?", (image_id, service_id))
    db.commit()
