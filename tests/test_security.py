import re

import pytest

from app import create_app


# --- Open redirect after login ---------------------------------------------

@pytest.mark.parametrize(
    "target",
    [
        "//evil.example/",
        "///evil.example/",
        "/\\evil.example/",
        "/\t/evil.example/",
        "https://evil.example/",
        "javascript:alert(1)",
        "evil.example",
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
    assert resp.headers["Location"] == "/reservations?x=1"


# --- CSRF ------------------------------------------------------------------

@pytest.fixture
def csrf_app(app):
    app.config["CSRF_ENABLED"] = True
    return app


@pytest.fixture
def csrf_client(csrf_app):
    return csrf_app.test_client()


def _token_from(html):
    m = re.search(rb'name="csrf_token" value="([^"]+)"', html)
    assert m, "form is missing its csrf_token field"
    return m.group(1).decode()


def _register(client):
    token = _token_from(client.get("/auth/register").data)
    resp = client.post(
        "/auth/register",
        data={"username": "alice", "password": "secret", "csrf_token": token},
    )
    assert resp.status_code == 302


def test_post_without_token_is_rejected(csrf_client):
    resp = csrf_client.post(
        "/auth/register", data={"username": "alice", "password": "secret"}
    )
    assert resp.status_code == 400


def test_post_with_wrong_token_is_rejected(csrf_client):
    csrf_client.get("/auth/register")  # establishes a session token
    resp = csrf_client.post(
        "/auth/register",
        data={"username": "alice", "password": "secret", "csrf_token": "nope"},
    )
    assert resp.status_code == 400


def test_form_token_round_trip(csrf_client):
    _register(csrf_client)
    page = csrf_client.get("/widgets/new").data
    resp = csrf_client.post(
        "/widgets/new",
        data={"name": "Room A", "csrf_token": _token_from(page)},
    )
    assert resp.status_code == 302


def test_header_token_accepted(csrf_client):
    _register(csrf_client)
    csrf_client.get("/widgets/new")  # rendering a form issues the session token
    with csrf_client.session_transaction() as sess:
        token = sess["_csrf_token"]
    resp = csrf_client.post(
        "/widgets/new", data={"name": "Room A"}, headers={"X-CSRF-Token": token}
    )
    assert resp.status_code == 302


def test_cross_site_cancel_is_blocked(csrf_client):
    _register(csrf_client)
    resp = csrf_client.post("/api/widgets", json={"name": "Room A"})
    widget_id = resp.get_json()["id"]
    resp = csrf_client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2030-01-01T09:00", "end_time": "2030-01-01T10:00"},
    )
    rid = resp.get_json()["id"]
    # A forged form post from another site carries the cookie but no token.
    resp = csrf_client.post(f"/reservations/{rid}/cancel")
    assert resp.status_code == 400
    assert len(csrf_client.get("/api/reservations").get_json()) == 1


def test_json_api_is_exempt(csrf_client):
    _register(csrf_client)
    resp = csrf_client.post("/api/widgets", json={"name": "Room A"})
    assert resp.status_code == 201


def test_csrf_enabled_by_default(tmp_path):
    app = create_app(
        {"TESTING": True, "DATABASE": str(tmp_path / "db.sqlite"), "SECRET_KEY": "t"}
    )
    assert app.config["CSRF_ENABLED"] is True


def test_every_post_form_has_token():
    """Static check: each <form method="post"> in the templates carries the token."""
    import pathlib

    templates = pathlib.Path(__file__).parent.parent / "app" / "templates"
    missing = []
    for path in templates.rglob("*.html"):
        text = path.read_text()
        for m in re.finditer(r'<form\s[^>]*method="post"[^>]*>', text, re.I):
            following = text[m.end(): m.end() + 200]
            if "csrf_token()" not in following:
                missing.append(f"{path.relative_to(templates)}:{text.count(chr(10), 0, m.start()) + 1}")
    assert not missing, f"POST forms without csrf_token: {missing}"
