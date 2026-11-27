import pytest

from bestbuy import create_app
from bestbuy.extensions import db


@pytest.fixture
def app():
    """A fresh in-memory database for each test, filled with the starting content."""
    app = create_app({"TESTING": True, "SQLALCHEMY_DATABASE_URI": "sqlite://", "SQLALCHEMY_ENGINE_OPTIONS": {},
                      "AUTO_LOAD_DEMO": True})
    with app.app_context():
        yield app
        db.session.remove()
        db.drop_all()


@pytest.fixture
def client(app):
    return app.test_client()
