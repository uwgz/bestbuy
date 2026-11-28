"""
POST /admin/upload: one photo from the admin pop-ups goes to Vercel Blob; answers {"url": ...}.
The browser makes each photo smaller first (at most 2000 px, JPEG), then sends them one at a time,
so many photos can be added at once without passing Vercel's 4.5 MB limit for one request.
"""
import re
import uuid

from flask import jsonify, request

from . import blob
from .admin import audit, bp, login_required
from .extensions import db

FOLDERS = {"products", "gear", "services", "portfolio"}
MAX_BYTES = 4 * 1024 * 1024
KINDS = {b"\xff\xd8\xff": ("image/jpeg", "jpg"), b"\x89PNG": ("image/png", "png"), b"RIFF": ("image/webp", "webp")}


def _kind(data):
    for magic, kind in KINDS.items():
        if data.startswith(magic) and (magic != b"RIFF" or data[8:12] == b"WEBP"):
            return kind
    return None


@bp.route("/upload", methods=["POST"])
@login_required
def upload():
    folder = request.form.get("folder", "")
    file = request.files.get("file")
    if folder not in FOLDERS or not file:
        return jsonify(error="Choose a photo."), 400
    data = file.read(MAX_BYTES + 1)
    if len(data) > MAX_BYTES:
        return jsonify(error="This photo is too big (4 MB at most)."), 400
    kind = _kind(data)
    if not kind:
        return jsonify(error="Only photos can be uploaded (JPEG, PNG or WebP)."), 400
    content_type, ext = kind
    name = re.sub(r"[^a-z0-9]+", "-", (request.form.get("name") or "photo").lower()).strip("-")[:40] or "photo"
    try:
        url = blob.put(f"{folder}/{name}-{uuid.uuid4().hex[:6]}.{ext}", data, content_type)
    except blob.BlobError as e:
        return jsonify(error=str(e)), 502
    audit("photo.upload", url)
    db.session.commit()
    return jsonify(url=url)
