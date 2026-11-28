"""
Vercel Blob: where uploaded photos are kept (public store).

The token comes from BLOB_READ_WRITE_TOKEN, which Vercel adds to the project when the Blob store is
connected to it (Vercel → Storage → your store → Projects). On your computer put it in .env.
Same requests as Vercel's own @vercel/blob library (API version 13), made with Python's urllib.
"""
import json
import os
import urllib.error
import urllib.parse
import urllib.request
import uuid

API_VERSION = "13"
ONE_YEAR = str(365 * 24 * 3600)


class BlobError(Exception):
    pass


def _token():
    token = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    if not token:
        raise BlobError("Photo uploads aren't set up: add BLOB_READ_WRITE_TOKEN in Vercel (or in .env on your computer).")
    return token


def _api(path):
    return os.environ.get("VERCEL_BLOB_API_URL", "https://vercel.com/api/blob") + path


def _request(method, path, body, headers):
    token = _token()
    parts = token.split("_")
    headers = {"authorization": f"Bearer {token}", "x-api-version": API_VERSION,
               "x-api-blob-request-id": uuid.uuid4().hex, "x-api-blob-request-attempt": "0",
               **({"x-vercel-blob-store-id": parts[3]} if len(parts) > 3 else {}), **headers}
    req = urllib.request.Request(_api(path), data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            code = json.loads(e.read()).get("error", {}).get("code", "")
        except Exception:
            code = ""
        raise BlobError({"forbidden": "Blob refused the upload: check BLOB_READ_WRITE_TOKEN.",
                         "file_too_large": "This photo is too big.",
                         "store_not_found": "The Blob store was not found: check BLOB_READ_WRITE_TOKEN.",
                         "store_suspended": "The Blob store is suspended in Vercel."}.get(code, f"Upload failed ({e.code} {code}).".replace(" )", ")")))
    except (urllib.error.URLError, TimeoutError):
        raise BlobError("Couldn't reach Vercel Blob. Try again.")


def put(pathname, data, content_type):
    """Uploads `data` as a public file under `pathname` (a random ending is added) and returns its URL."""
    query = urllib.parse.urlencode({"pathname": pathname})
    result = _request("PUT", f"/?{query}", data, {
        "x-vercel-blob-access": "public", "x-content-type": content_type,
        "x-add-random-suffix": "1", "x-cache-control-max-age": ONE_YEAR,
        "x-content-length": str(len(data)),
    })
    if not result.get("url"):
        raise BlobError("Blob didn't return the photo's address.")
    return result["url"]


def delete(urls):
    if urls:
        _request("POST", "/delete", json.dumps({"urls": list(urls)}).encode(), {"content-type": "application/json"})
