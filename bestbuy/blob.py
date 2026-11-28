"""
Vercel Blob: where uploaded photos are kept (public store).

Two ways to sign the uploads, the same as Vercel's own @vercel/blob library (API version 13):
  1. BLOB_STORE_ID (added when the Blob store is connected to the project) + the Vercel OIDC token that Vercel
     gives every request of a deployed site (header x-vercel-oidc-token; VERCEL_OIDC_TOKEN on your computer
     after `vercel env pull`). This is what newer Vercel projects use.
  2. BLOB_READ_WRITE_TOKEN, if the project has one (older connections, or put in .env on your computer).
Requests are made with Python's urllib.
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


def _oidc_token():
    try:
        from flask import has_request_context, request
        if has_request_context() and request.headers.get("x-vercel-oidc-token"):
            return request.headers["x-vercel-oidc-token"].strip()
    except ImportError:
        pass
    token = os.environ.get("VERCEL_OIDC_TOKEN", "").strip()
    path = os.environ.get("VERCEL_OIDC_TOKEN_FILE", "")
    if not token and path and os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            token = f.read().strip()
    return token


def _auth():
    """(token, store id) for the Authorization and x-vercel-blob-store-id headers."""
    read_write = os.environ.get("BLOB_READ_WRITE_TOKEN", "").strip()
    store = os.environ.get("BLOB_STORE_ID", "").strip()
    oidc = _oidc_token()
    if oidc and store:                                  # newer projects: Vercel's own token + the store's id
        return oidc, store[len("store_"):] if store.startswith("store_") else store
    if read_write:                                      # older projects: vercel_blob_rw_<store>_<secret>
        parts = read_write.split("_")
        return read_write, parts[3] if len(parts) > 3 else ""
    if store:
        raise BlobError("Photo uploads need Vercel's sign-in token, which only a deployed site has. "
                        "On your computer, run `vercel env pull` or put BLOB_READ_WRITE_TOKEN in .env.")
    raise BlobError("Photo uploads aren't set up: connect the Blob store to the project in Vercel (Storage → your store → Projects).")


def _api(path):
    return os.environ.get("VERCEL_BLOB_API_URL", "https://vercel.com/api/blob") + path


def _request(method, path, body, headers):
    token, store = _auth()
    headers = {"authorization": f"Bearer {token}", "x-api-version": API_VERSION,
               "x-api-blob-request-id": uuid.uuid4().hex, "x-api-blob-request-attempt": "0",
               **({"x-vercel-blob-store-id": store} if store else {}), **headers}
    req = urllib.request.Request(_api(path), data=body, method=method, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return json.loads(res.read() or b"{}")
    except urllib.error.HTTPError as e:
        try:
            code = json.loads(e.read()).get("error", {}).get("code", "")
        except Exception:
            code = ""
        raise BlobError({"forbidden": "Vercel Blob refused the upload: check the Blob store is connected to this project.",
                         "file_too_large": "This photo is too big.",
                         "store_not_found": "The Blob store was not found: check BLOB_STORE_ID in Vercel.",
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
