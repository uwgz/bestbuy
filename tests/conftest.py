import io
import os
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app import create_app  # noqa: E402
import sample_data  # noqa: E402

PASSWORD = "correct-horse-battery"

# Every test runs on SQLite, and also on PostgreSQL (like Neon) when a test server is given:
#   TEST_POSTGRES_URL=postgresql://postgres@127.0.0.1:5432/postgres python -m pytest
PG_URL = os.environ.get("TEST_POSTGRES_URL", "")
BACKENDS = ["sqlite"] + (["postgres"] if PG_URL else [])


@pytest.fixture(params=BACKENDS)
def backend(request):
    return request.param


@pytest.fixture
def pg_schema():
    """A fresh, empty PostgreSQL schema for one test; returns (DATABASE_URL, driver)."""
    import uuid
    import pgwire
    name = "t_" + uuid.uuid4().hex[:12]
    admin = pgwire.connect(PG_URL)
    admin.cursor().execute(f"CREATE SCHEMA {name}")
    sep = "&" if "?" in PG_URL else "?"
    yield f"{PG_URL}{sep}options=-csearch_path%3D{name}", pgwire
    admin.cursor().execute(f"DROP SCHEMA {name} CASCADE")
    admin.close()


def make_app(tmp_path, backend, request=None, **overrides):
    if backend == "postgres":
        url, driver = request.getfixturevalue("pg_schema")
        overrides.update(DATABASE_URL=url, PG_DRIVER=driver)
    return create_app("testing", INSTANCE_DIR=tmp_path, DATABASE=tmp_path / "test.db", UPLOAD_DIR=tmp_path / "uploads",
                      **overrides)


@pytest.fixture
def app(tmp_path, backend, request):
    app = make_app(tmp_path, backend, request)
    with app.test_request_context():
        sample_data.load()                   # the real site starts empty; tests use sample content
    from app.security import _failures
    _failures.clear()
    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def owner(client):
    client.post("/altar/setup", data={"name": "Owner", "email": "owner@example.com", "password": PASSWORD, "confirm": PASSWORD})
    return client


def photo_bytes(color=(20, 20, 20), size=(400, 300), white_border=True, fmt="PNG"):
    img = Image.new("RGB", size, (255, 255, 255) if white_border else color)
    if white_border:
        img.paste(Image.new("RGB", (size[0] // 2, size[1] // 2), color), (size[0] // 4, size[1] // 4))
    buf = io.BytesIO()
    img.save(buf, fmt)
    buf.seek(0)
    return buf
