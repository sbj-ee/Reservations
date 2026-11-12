import base64
import os
import secrets
import tempfile

import pytest
from flask.testing import FlaskClient

from app import create_app
from app.db import get_db
from app.security import CSRF_FIELD, SESSION_KEY as SESSION_CSRF_KEY


class CSRFClient(FlaskClient):
    """Test client that adds the session's CSRF token to form POSTs, like a real
    browser submitting a rendered form. Pass ``csrf=False`` to send a POST without
    it (to test rejection)."""

    def csrf_token(self):
        with self.session_transaction() as sess:
            token = sess.get(SESSION_CSRF_KEY)
            if not token:
                token = sess[SESSION_CSRF_KEY] = secrets.token_urlsafe(32)
        return token

    def post(self, path, *args, csrf=True, **kwargs):
        data = kwargs.get("data")
        if csrf and "json" not in kwargs and not path.startswith("/api/") and (
            data is None or isinstance(data, dict)
        ):
            data = dict(data or {})
            data.setdefault(CSRF_FIELD, self.csrf_token())
            kwargs["data"] = data
        return super().post(path, *args, **kwargs)


@pytest.fixture
def app():
    db_fd, db_path = tempfile.mkstemp(suffix=".sqlite")
    app = create_app(
        {"TESTING": True, "DATABASE": db_path, "SECRET_KEY": "test"}
    )
    app.test_client_class = CSRFClient
    yield app
    os.close(db_fd)
    os.unlink(db_path)


@pytest.fixture
def client(app):
    return app.test_client()


class AuthActions:
    def __init__(self, client):
        self._client = client

    def register(self, username="alice", password="secret", email=None, phone=None):
        data = {"username": username, "password": password}
        if email is not None:
            data["email"] = email
        if phone is not None:
            data["phone"] = phone
        return self._client.post("/auth/register", data=data)

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


@pytest.fixture
def user_row(app):
    def _user_row(username):
        with app.app_context():
            r = get_db().execute(
                "SELECT * FROM user WHERE username = ?", (username,)
            ).fetchone()
            return dict(r) if r else None

    return _user_row


@pytest.fixture
def notifications(app):
    def _notifications():
        with app.app_context():
            return [
                dict(r)
                for r in get_db()
                .execute("SELECT * FROM notification ORDER BY id")
                .fetchall()
            ]

    return _notifications


def basic_auth_header(username="alice", password="secret"):
    token = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {token}"}
