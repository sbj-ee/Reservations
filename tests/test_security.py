import os

import pytest
import re
import stat

from flask import Flask

from app import security
from tests.conftest import basic_auth_header


def _token_from(html):
    m = re.search(r'name="csrf_token" value="([^"]+)"', html)
    assert m, "rendered form should include a CSRF token"
    return m.group(1)


# --- CSRF -------------------------------------------------------------------

def test_form_post_without_token_is_rejected(client, user_row):
    resp = client.post(
        "/auth/register", data={"username": "mallory", "password": "x"}, csrf=False
    )
    assert resp.status_code == 400
    assert user_row("mallory") is None


def test_form_post_with_wrong_token_is_rejected(client, auth, user_row):
    auth.register()
    client.get("/widgets")  # establishes a session token
    resp = client.post(
        "/widgets/new", data={"name": "Forged", "csrf_token": "nope"}, csrf=False
    )
    assert resp.status_code == 400
    assert b"Forged" not in client.get("/widgets").data


def test_forged_admin_action_is_rejected(client, auth, make_admin, user_row):
    auth.register("bob")
    auth.logout()
    auth.register("admin")
    make_admin("admin")
    bob = user_row("bob")["id"]
    resp = client.post(f"/admin/users/{bob}/delete", csrf=False)
    assert resp.status_code == 400
    assert user_row("bob") is not None


def test_rendered_token_round_trip(client, user_row):
    """End to end like a browser: fetch the form, submit with its token."""
    token = _token_from(client.get("/auth/register").get_data(as_text=True))
    resp = client.post(
        "/auth/register",
        data={"username": "carol", "password": "pw", "csrf_token": token},
        csrf=False,
    )
    assert resp.status_code == 302
    assert user_row("carol") is not None


def test_every_post_form_has_a_token(client, auth, make_admin):
    auth.register("bob")  # admin pages only show user actions for other users
    auth.logout()
    auth.register("admin")
    make_admin("admin")
    client.post("/api/widgets", json={"name": "Room A"})
    client.post(
        "/api/widgets/1/reservations",
        json={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"},
    )
    pages = [
        "/widgets/new", "/widgets/1", "/reservations", "/reservations/1/edit",
        "/account", "/admin/users", "/admin/users/1/edit", "/admin/widgets",
        "/admin/widgets/1/edit", "/admin/reservations",
    ]
    auth.logout()
    anon_pages = ["/auth/login", "/auth/register", "/auth/forgot"]
    for page in anon_pages:
        html = client.get(page).get_data(as_text=True)
        assert html.count('method="post"') == html.count('name="csrf_token"'), page
    auth.login("admin")
    for page in pages:
        html = client.get(page).get_data(as_text=True)
        assert 'method="post"' in html, page
        assert html.count('method="post"') == html.count('name="csrf_token"'), page


def test_api_json_with_session_still_works(client, auth):
    auth.register()
    assert client.post("/api/widgets", json={"name": "Room A"}).status_code == 201


def test_api_post_requires_json(client, auth):
    """A cross-site form can't send JSON, so non-JSON API POSTs are refused."""
    auth.register()
    resp = client.post("/api/widgets", data={"name": "Forged"})
    assert resp.status_code == 415
    assert client.get("/api/widgets").get_json() == []


def test_api_basic_auth_unaffected(client, auth):
    auth.register()
    auth.logout()
    resp = client.post(
        "/api/widgets", json={"name": "Room B"}, headers=basic_auth_header()
    )
    assert resp.status_code == 201


def test_session_cookie_is_samesite_lax(client):
    resp = client.post(
        "/auth/register", data={"username": "dave", "password": "pw"}
    )
    cookie = resp.headers.get("Set-Cookie", "")
    assert "SameSite=Lax" in cookie and "HttpOnly" in cookie


# --- Secret key -------------------------------------------------------------

def test_secret_key_created_persisted_and_private(tmp_path):
    key = security.load_or_create_secret_key(str(tmp_path))
    assert len(key) == 64
    assert security.load_or_create_secret_key(str(tmp_path)) == key
    mode = stat.S_IMODE(os.stat(tmp_path / "secret_key").st_mode)
    assert mode == 0o600
    assert [p.name for p in tmp_path.iterdir()] == ["secret_key"]  # no temp files left


def test_missing_secret_key_never_falls_back_to_a_default(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path))
    app.config["SECRET_KEY"] = None
    security.init_app(app)
    assert app.config["SECRET_KEY"] == (tmp_path / "secret_key").read_text().strip()


def test_explicit_secret_key_is_kept(tmp_path):
    app = Flask(__name__, instance_path=str(tmp_path))
    app.config["SECRET_KEY"] = "from-env"
    security.init_app(app)
    assert app.config["SECRET_KEY"] == "from-env"
    assert not (tmp_path / "secret_key").exists()

# --- Open redirect after login ---------------------------------------------

@pytest.mark.parametrize(
    "target",
    [
        "http://evil.example.com/",
        "https://evil.example.com/",
        "//evil.example.com",
        "///evil.example.com/",
        "/\\evil.example.com/",
        "/\t/evil.example.com/",
        "javascript:alert(1)",
        "evil.example.com",
    ],
)
def test_login_rejects_offsite_next(client, auth, target):
    auth.register()
    auth.logout()
    resp = client.post(
        "/auth/login",
        data={"username": "alice", "password": "secret", "next": target},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/widgets"


def test_login_follows_local_next(client, auth):
    auth.register()
    auth.logout()
    resp = client.post(
        "/auth/login",
        data={"username": "alice", "password": "secret", "next": "/reservations?x=1"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/reservations?x=1"


def test_login_without_next_goes_to_default(client, auth):
    auth.register()
    auth.logout()
    resp = client.post(
        "/auth/login",
        data={"username": "alice", "password": "secret"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"] == "/widgets"
