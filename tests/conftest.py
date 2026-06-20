import uuid
import pytest
from app import app as flask_app
from database.db import create_user


@pytest.fixture
def app():
    flask_app.config["TESTING"] = True
    yield flask_app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture
def empty_user_id():
    email = f"empty_{uuid.uuid4().hex[:8]}@test.com"
    return create_user("Test Empty", email, "testpass123")
