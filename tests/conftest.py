import base64
import os
import tempfile

import pytest

from app import create_app


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


def basic_auth_header(username="alice", password="secret"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}
