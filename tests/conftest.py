import base64
import os
import tempfile

import pytest

from app import create_app
from app.db import get_db


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    app = create_app(
        {"TESTING": True, "DATABASE": db_path, "SECRET_KEY": "test"}
    )
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


class AuthActions:
    def __init__(self, client):
        self._client = client

    def register(self, username="alice", password="secret"):
        return self._client.post(
            "/auth/register", data={"username": username, "password": password}
        )

    def login(self, username="alice", password="secret"):
        return self._client.post(
            "/auth/login", data={"username": username, "password": password}
        )

    def logout(self):
        return self._client.get("/auth/logout")


@pytest.fixture
def auth(client):
    return AuthActions(client)


@pytest.fixture
def make_admin(app):
    def _make_admin(username):
        with app.app_context():
            db = get_db()
            db.execute("UPDATE user SET is_admin = 1 WHERE username = ?", (username,))
            db.commit()

    return _make_admin


@pytest.fixture
def is_admin(app):
    def _is_admin(username):
        with app.app_context():
            row = get_db().execute(
                "SELECT is_admin FROM user WHERE username = ?", (username,)
            ).fetchone()
            return bool(row and row["is_admin"])

    return _is_admin


def basic_auth_header(username="alice", password="secret"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}
