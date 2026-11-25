"""Portfolio photos (the studio's own work)."""
import re

from ..db import execute, query
from .. import images

CATEGORIES = ["Portrait", "Wedding", "Event", "Product", "Landscape", "Family"]


def clean_instagram(text):
    """'@eric', 'eric' or 'https://instagram.com/eric/' -> 'eric' (empty if it doesn't look like a handle)."""
    text = (text or "").strip()
    m = re.search(r"instagram\.com/([A-Za-z0-9_.]+)", text)
    handle = m.group(1) if m else text.lstrip("@")
    return handle if re.fullmatch(r"[A-Za-z0-9_.]{1,30}", handle) else ""


def list_items():
    return [dict(r) | {"url": images.media_url(r["filename"]),
                       "instagram_url": f"https://instagram.com/{r['instagram']}" if r["instagram"] else None}
            for r in query("SELECT * FROM portfolio ORDER BY position, id DESC")]


def add(filename, title="", category="Portrait", instagram=""):
    pos = query("SELECT COALESCE(MAX(position), 0) + 1 AS n FROM portfolio", one=True)["n"]
    return execute("INSERT INTO portfolio (filename, title, category, instagram, position) VALUES (?, ?, ?, ?, ?)",
                   (filename, title, category, clean_instagram(instagram), pos))


def update(item_id, title, category, position, instagram=""):
    execute("UPDATE portfolio SET title = ?, category = ?, position = ?, instagram = ? WHERE id = ?",
            (title, category, position, clean_instagram(instagram), item_id))


def delete(item_id):
    row = query("SELECT filename FROM portfolio WHERE id = ?", (item_id,), one=True)
    if row:
        images.delete_file(row["filename"])
        execute("DELETE FROM portfolio WHERE id = ?", (item_id,))



def recent_work(limit=12):
    """Only the photos uploaded to the portfolio (Admin → Portfolio), newest first."""
    return list_items()[:limit]
