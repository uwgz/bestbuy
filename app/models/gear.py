"""Studio gear — the cameras, lenses and tools the studio uses (not sold in the shop)."""
from ..db import execute, query
from .. import images
from .products import slugify

EDITABLE = ("name", "role", "description", "is_active", "position")


def _decorate(row):
    g = dict(row)
    g["image"] = images.media_url(row["filename"]) if row["filename"] else None
    return g


def list_gear(active_only=True):
    rows = query("SELECT * FROM studio_gear" + (" WHERE is_active = 1" if active_only else "") + " ORDER BY position, id")
    return [_decorate(r) for r in rows]


def get_by_slug(slug):
    row = query("SELECT * FROM studio_gear WHERE slug = ?", (slug,), one=True)
    return _decorate(row) if row else None


def _unique_slug(name, exclude_id=None):
    base = slugify(name)
    slug, n = base, 2
    while query("SELECT 1 FROM studio_gear WHERE slug = ? AND id <> ?", (slug, exclude_id or 0), one=True):
        slug, n = f"{base}-{n}", n + 1
    return slug


def create(data, filename=""):
    data = {k: data[k] for k in EDITABLE if k in data}
    data["slug"] = _unique_slug(data["name"])
    data["filename"] = filename
    data.setdefault("position", query("SELECT COALESCE(MAX(position), 0) + 1 AS n FROM studio_gear", one=True)["n"])
    execute(f"INSERT INTO studio_gear ({', '.join(data)}) VALUES ({', '.join('?' * len(data))})", tuple(data.values()))
    return data["slug"]


def update(gear_id, data, filename=None):
    data = {k: data[k] for k in EDITABLE if k in data}
    old = query("SELECT name, filename FROM studio_gear WHERE id = ?", (gear_id,), one=True)
    if old and data.get("name") and data["name"] != old["name"]:
        data["slug"] = _unique_slug(data["name"], exclude_id=gear_id)
    if filename:                       # new photo replaces the old one
        images.delete_file(old["filename"])
        data["filename"] = filename
    execute(f"UPDATE studio_gear SET {', '.join(f'{k} = ?' for k in data)} WHERE id = ?", (*data.values(), gear_id))
    return query("SELECT slug FROM studio_gear WHERE id = ?", (gear_id,), one=True)["slug"]


def delete(gear_id):
    row = query("SELECT filename FROM studio_gear WHERE id = ?", (gear_id,), one=True)
    if row:
        images.delete_file(row["filename"])
        execute("DELETE FROM studio_gear WHERE id = ?", (gear_id,))
