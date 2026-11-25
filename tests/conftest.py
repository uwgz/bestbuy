import io
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parent))
from app import create_app  # noqa: E402
import sample_data  # noqa: E402

PASSWORD = "correct-horse-battery"


@pytest.fixture
def app(tmp_path):
    app = create_app("testing", INSTANCE_DIR=tmp_path, DATABASE=tmp_path / "test.db", UPLOAD_DIR=tmp_path / "uploads")
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
