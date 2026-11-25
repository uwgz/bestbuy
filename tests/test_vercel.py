"""The Vercel setup: Turso database + Blob photos (using offline stand-ins from fakes.py)."""
import pytest

from app import create_app
from conftest import PASSWORD, photo_bytes
from fakes import FakeBlob, FakeTurso


@pytest.fixture
def cloud(tmp_path):
    turso = FakeTurso(tmp_path / "remote.db")
    blob = FakeBlob()
    app = create_app("testing", INSTANCE_DIR=tmp_path / "inst", TURSO_DATABASE_URL=turso.url,
                     TURSO_AUTH_TOKEN=FakeTurso.TOKEN, MEDIA_STORAGE="blob", BLOB_CLIENT=blob)
    import sample_data
    with app.test_request_context():
        sample_data.load()
    from app.security import _failures
    _failures.clear()
    yield app, turso, blob
    turso.stop()


def test_database_lives_in_turso(cloud):
    app, turso, blob = cloud
    assert not (app.config["DATABASE"]).exists()          # nothing written to the local disk
    assert turso.requests > 0
    client = app.test_client()
    assert client.get("/").status_code == 200
    html = client.get("/shop").get_data(as_text=True)
    assert "Noise-Cancelling Headphones" in html
    # photos are sent to Blob and the pages point at Blob addresses
    assert blob.files and all(ct and ct.startswith("image/") for _b, ct, _c in blob.files.values())
    assert FakeBlob.BASE in client.get("/photography").get_data(as_text=True)


def test_admin_on_turso_and_blob(cloud):
    app, turso, blob = cloud
    c = app.test_client()
    c.post("/altar/setup", data={"name": "Owner", "email": "o@example.com", "password": PASSWORD, "confirm": PASSWORD})
    before = len(blob.files)
    r = c.post("/altar/products/new", content_type="multipart/form-data", data={
        "name": "Cloud Cam", "category": "cameras", "price": "500", "discount_percent": "0", "is_active": "1",
        "in_stock": "1", "cutout": "1", "photos": (photo_bytes(), "cam.png")})
    assert r.status_code == 302
    assert len(blob.files) == before + 1
    url = [u for u in blob.files if u not in blob.deleted][-1]
    data, ctype, max_age = blob.files[url]
    assert ctype == "image/webp" and data[:4] == b"RIFF" and max_age >= 60 * 60 * 24 * 30
    page = c.get("/product/cloud-cam").get_data(as_text=True)
    assert url in page
    # deleting the product removes its photo from Blob, and its photo rows (ON DELETE CASCADE)
    with app.app_context():
        from app.db import query
        pid = query("SELECT id FROM products WHERE slug = 'cloud-cam'", one=True)["id"]
    c.post(f"/altar/products/{pid}/delete")
    assert url in blob.deleted
    with app.app_context():
        from app.db import query
        assert query("SELECT COUNT(*) AS n FROM product_images pi LEFT JOIN products p ON p.id = pi.product_id "
                     "WHERE p.id IS NULL", one=True)["n"] == 0


def test_turso_rows_behave_like_sqlite(cloud):
    app, _t, _b = cloud
    with app.app_context():
        from app.db import execute, query
        new_id = execute("INSERT INTO messages (name, email, message) VALUES (?, ?, ?)", ("Eric", "e@x.com", "Hi ✓"))
        row = query("SELECT * FROM messages WHERE id = ?", (new_id,), one=True)
        assert row["name"] == "Eric" and row[0] == new_id and dict(row)["message"] == "Hi ✓"
        assert query("SELECT NULL AS n, 1.5 AS f", one=True)["f"] == 1.5


def test_turso_errors_are_raised(cloud):
    app, _t, _b = cloud
    from app.turso import Error
    with app.app_context(), pytest.raises(Error):
        from app.db import query
        query("SELECT * FROM no_such_table")


def test_media_url_keeps_blob_addresses(app):
    from app.images import media_url
    with app.test_request_context():
        assert media_url("https://x.public.blob.vercel-storage.com/a.webp").startswith("https://x.")
        assert media_url("products/a.webp") == "/media/products/a.webp"
        assert media_url("") is None


def test_vercel_entrypoint_exposes_app(monkeypatch, tmp_path):
    import importlib
    import config
    monkeypatch.setenv("SECRET_KEY", "x" * 32)
    monkeypatch.setattr(config.Config, "INSTANCE_DIR", tmp_path)   # keep the project's instance/ clean
    mod = importlib.import_module("wsgi")
    assert mod.app.name == "app" and not mod.app.debug


def test_vercel_limits(monkeypatch):
    """With VERCEL set: files in /tmp, a 4 MB browser-side upload limit, and SECRET_KEY required."""
    import importlib
    import config
    monkeypatch.setenv("VERCEL", "1")
    monkeypatch.delenv("INSTANCE_DIR", raising=False)
    try:
        cfg = importlib.reload(config)
        assert str(cfg.Config.INSTANCE_DIR).startswith("/tmp/")
        assert cfg.Config.UPLOAD_REQUEST_LIMIT <= 4_000_000 < cfg.Config.MAX_CONTENT_LENGTH <= 4.5 * 1024 * 1024
        import app as app_pkg
        importlib.reload(app_pkg)
        monkeypatch.delenv("SECRET_KEY", raising=False)
        cfg.ProductionConfig.SECRET_KEY = ""
        with pytest.raises(RuntimeError, match="SECRET_KEY"):
            app_pkg.create_app("production", INSTANCE_DIR="/tmp/ve-test-vercel")
    finally:
        monkeypatch.delenv("VERCEL")
        importlib.reload(config)
        import app as app_pkg
        importlib.reload(app_pkg)
