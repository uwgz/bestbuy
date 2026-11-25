"""
Photo uploads: check, resize, optionally cut out a white background, save as WebP.

Where photos are kept (config MEDIA_STORAGE):
  local  instance/uploads/<folder>/<file>, served by the app at /media/<folder>/<file>
  blob   Vercel Blob (public store); the database keeps the full https:// address

Templates never build photo addresses themselves: they use `media_url(filename)`,
which works for both.
"""
import io
import uuid
from pathlib import Path

from flask import current_app, url_for
from PIL import Image, ImageChops, ImageDraw, ImageFilter, ImageOps, UnidentifiedImageError

ALLOWED_FORMATS = {"JPEG", "PNG", "WEBP", "AVIF", "GIF", "MPO"}
CONTENT_TYPES = {"webp": "image/webp", "jpg": "image/jpeg", "jpeg": "image/jpeg", "png": "image/png", "avif": "image/avif"}
YEAR = 60 * 60 * 24 * 365


class ImageError(ValueError):
    pass


# ---------------------------------------------------------------- storage
def _upload_dir():
    return Path(current_app.config["UPLOAD_DIR"])


def _using_blob():
    return current_app.config.get("MEDIA_STORAGE") == "blob"


def _blob():
    """The Vercel Blob client (tests can put a stand-in in config BLOB_CLIENT)."""
    client = current_app.config.get("BLOB_CLIENT")
    if client is None:
        from vercel.blob import sync as client   # pip install vercel
    return client


def _store(name, data):
    """Keep the bytes under `name` (folder/file.ext); returns what the database should remember."""
    if _using_blob():
        ext = name.rsplit(".", 1)[-1].lower()
        result = _blob().put_blob(name, data, access="public", content_type=CONTENT_TYPES.get(ext),
                                  cache_control_max_age=YEAR)   # names are unique, so cache for a long time
        return result.url
    path = _upload_dir() / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return name


def media_url(filename):
    """Address of a stored photo for <img src>."""
    if not filename:
        return None
    if filename.startswith(("https://", "http://")):
        return filename
    return url_for("media", filename=filename)


def delete_file(filename):
    if not filename:
        return
    if filename.startswith(("https://", "http://")):
        if _using_blob():
            try:
                _blob().delete_blob(filename)
            except Exception as exc:   # a missing photo must never block deleting a product
                current_app.logger.warning("Could not delete %s from Blob: %s", filename, exc)
        return
    path = (_upload_dir() / filename).resolve()
    if _upload_dir().resolve() in path.parents and path.exists():
        path.unlink()


def _new_name(folder, ext="webp"):
    return f"{folder}/{uuid.uuid4().hex[:16]}.{ext}"


# ---------------------------------------------------------------- processing
def open_image(stream):
    try:
        img = Image.open(stream)
        if img.format not in ALLOWED_FORMATS:
            raise ImageError("Please upload a JPG, PNG, WebP or AVIF photo.")
        img.load()
    except (UnidentifiedImageError, OSError) as exc:
        raise ImageError("That file isn't a photo we can read.") from exc
    return ImageOps.exif_transpose(img)


def remove_white_background(img, thresh=238):
    """Make near-white areas that touch the edges transparent (studio product shots).

    Pure Pillow: near-white pixels are found per channel, then the white region connected to the
    border is flood-filled on a small copy (fast) and scaled back up to the full photo.
    """
    rgb = img.convert("RGB")
    r, g, b = rgb.split()
    low = ImageChops.darker(ImageChops.darker(r, g), b)     # min channel
    high = ImageChops.lighter(ImageChops.lighter(r, g), b)  # max channel
    light = ImageChops.multiply(low.point(lambda v: 255 if v >= thresh else 0),
                                ImageChops.subtract(high, low).point(lambda v: 255 if v < 14 else 0))

    # find the white area joined to the edges on a copy of at most 400 px
    small = light.copy()
    small.thumbnail((400, 400), Image.NEAREST)
    small = small.point(lambda v: 255 if v > 127 else 0)
    w, h = small.size
    seeds = [(x, y) for x in range(w) for y in (0, h - 1)] + [(x, y) for y in range(h) for x in (0, w - 1)]
    found = False
    for xy in seeds:
        if small.getpixel(xy) == 255:
            ImageDraw.floodfill(small, xy, 128)
            found = True
    if not found:
        return img  # no white background found — keep the photo as it is
    bg_small = small.point(lambda v: 255 if v == 128 else 0)
    # grow by one small pixel so the scaled-up edge covers the border, then keep only truly white pixels
    bg = bg_small.filter(ImageFilter.MaxFilter(3)).resize(rgb.size, Image.BILINEAR).point(lambda v: 255 if v > 0 else 0)
    bg = ImageChops.multiply(bg, light)

    alpha = ImageChops.invert(bg).filter(ImageFilter.MinFilter(3)).filter(ImageFilter.GaussianBlur(1.1))
    out = rgb.convert("RGBA")
    out.putalpha(alpha)
    box = out.getbbox()
    if box:
        out = out.crop(box)
    side = int(max(out.size) * 1.06)  # square canvas with a little breathing room
    canvas = Image.new("RGBA", (side, side), (0, 0, 0, 0))
    canvas.paste(out, ((side - out.width) // 2, (side - out.height) // 2), out)
    return canvas


def save_image(img, folder, cutout=False):
    if img.mode not in ("RGB", "RGBA"):
        img = img.convert("RGBA" if "A" in img.getbands() or img.mode == "P" else "RGB")
    max_side = current_app.config.get("MAX_IMAGE_SIDE", 1600)
    img.thumbnail((max_side, max_side), Image.LANCZOS)
    if cutout:
        img = remove_white_background(img)
    buf = io.BytesIO()
    img.save(buf, "WEBP", quality=86, method=4)   # re-encoding also strips hidden metadata (GPS …)
    return _store(_new_name(folder), buf.getvalue())


def save_upload(file_storage, folder, cutout=False):
    """Validate and store one uploaded photo. Returns what to keep in the database."""
    if not file_storage or not file_storage.filename:
        raise ImageError("Choose a photo first.")
    return save_image(open_image(file_storage.stream), folder, cutout=cutout)
