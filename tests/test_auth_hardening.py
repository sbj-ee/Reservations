"""Login throttling, password policy, POST-only logout, and notification time zones."""
import os
import tempfile
from datetime import timedelta
from zoneinfo import ZoneInfo

import pytest

from app import create_app, throttle
from app.security import DEFAULT_MIN_PASSWORD_LENGTH
from tests.conftest import basic_auth_header

GOOD = "correct-horse"


def _login(client, username="alice", password=GOOD, ip=None):
    kw = {"environ_base": {"REMOTE_ADDR": ip}} if ip else {}
    return client.post(
        "/auth/login", data={"username": username, "password": password}, **kw
    )


def _logged_in(client):
    return client.get("/account").status_code == 200


@pytest.fixture
def alice(client, auth):
    auth.register("alice", GOOD)
    auth.logout()


# --- Login throttling --------------------------------------------------------

def test_throttled_after_five_failures_even_with_right_password(client, alice):
    for _ in range(5):
        assert _login(client, password="wrong").status_code == 200
    resp = _login(client)  # correct password, but throttled
    assert resp.status_code == 429
    assert b"Too many failed sign-in attempts" in resp.data
    assert not _logged_in(client)


def test_success_resets_the_account_ip_counter(client, auth, alice):
    for _ in range(4):
        _login(client, password="wrong")
    assert _login(client).status_code == 302
    auth.logout()
    for _ in range(4):
        _login(client, password="wrong")
    assert _login(client).status_code == 302


def test_lockout_is_per_ip_so_owner_elsewhere_can_still_log_in(client, alice):
    for _ in range(5):
        _login(client, password="wrong", ip="203.0.113.9")
    assert _login(client, ip="203.0.113.9").status_code == 429
    assert _login(client, ip="198.51.100.7").status_code == 302


def test_one_ip_spraying_many_accounts_is_throttled(client, alice):
    for i in range(20):
        _login(client, username=f"user{i}", password="wrong")
    assert _login(client).status_code == 429


def test_throttle_expires_after_window(client, alice, monkeypatch):
    for _ in range(5):
        _login(client, password="wrong")
    assert _login(client).status_code == 429
    real_now = throttle._now
    monkeypatch.setattr(throttle, "_now", lambda: real_now() + timedelta(minutes=16))
    assert _login(client).status_code == 302


def test_api_basic_auth_is_throttled(client, alice):
    bad = basic_auth_header("alice", "wrong")
    for _ in range(5):
        assert client.get("/api/reservations", headers=bad).status_code == 401
    resp = client.get("/api/reservations", headers=basic_auth_header("alice", GOOD))
    assert resp.status_code == 429
    assert int(resp.headers["Retry-After"]) > 0


def test_account_current_password_check_is_throttled(client, alice):
    _login(client)
    form = {"action": "password", "current_password": "wrong",
            "new_password": "new-password-1", "confirm_password": "new-password-1"}
    for _ in range(5):
        assert b"Current password is incorrect" in client.post("/account", data=form).data
    resp = client.post("/account", data={**form, "current_password": GOOD})
    assert b"Too many incorrect attempts" in resp.data


def test_failures_are_pruned_after_window(app, client, alice, monkeypatch):
    for _ in range(3):
        _login(client, password="wrong")
    real_now = throttle._now
    monkeypatch.setattr(throttle, "_now", lambda: real_now() + timedelta(minutes=16))
    _login(client, password="wrong")  # recording a failure prunes old rows
    with app.app_context():
        from app.db import get_db
        n = get_db().execute("SELECT COUNT(*) FROM login_failure").fetchone()[0]
    assert n == 3  # just the newest failure's three keys


# --- Password policy ---------------------------------------------------------

@pytest.fixture
def real_policy(app):
    app.config["MIN_PASSWORD_LENGTH"] = DEFAULT_MIN_PASSWORD_LENGTH


def test_register_rejects_short_password(client, user_row, real_policy):
    resp = client.post(
        "/auth/register", data={"username": "bob", "password": "short"},
        follow_redirects=True,
    )
    assert b"at least 8 characters" in resp.data
    assert user_row("bob") is None
    client.post("/auth/register", data={"username": "bob", "password": "long-enough"})
    assert user_row("bob") is not None


def test_account_change_rejects_short_password(client, auth, real_policy):
    auth.register("alice", GOOD)
    resp = client.post("/account", data={
        "action": "password", "current_password": GOOD,
        "new_password": "short", "confirm_password": "short"})
    assert b"at least 8 characters" in resp.data
    auth.logout()
    assert _login(client).status_code == 302  # old password still works


def test_admin_edit_rejects_short_password_without_partial_save(
    client, auth, make_admin, user_row, real_policy
):
    auth.register("bob", GOOD)
    auth.logout()
    auth.register("admin", GOOD)
    make_admin("admin")
    bob = user_row("bob")
    resp = client.post(f"/admin/users/{bob['id']}/edit", data={
        "username": "robert", "email": "", "phone": "", "new_password": "short"})
    assert b"at least 8 characters" in resp.data
    assert user_row("bob") is not None and user_row("robert") is None


def test_reset_rejects_short_password(app, client, auth, real_policy):
    import hashlib
    auth.register("alice", GOOD)
    auth.logout()
    with app.app_context():
        from app import models
        uid = models.find_user_by_identifier("alice")["id"]
        models.create_password_reset(
            uid, hashlib.sha256(b"tok").hexdigest(), "2999-01-01 00:00:00")
    resp = client.post("/auth/reset/tok", data={
        "new_password": "short", "confirm_password": "short"})
    assert b"at least 8 characters" in resp.data
    assert _login(client).status_code == 302


def test_cli_create_admin_rejects_short_password(app, real_policy):
    result = app.test_cli_runner().invoke(args=["create-admin", "root", "short"])
    assert result.exit_code != 0
    assert "at least 8 characters" in result.output


def test_overlong_password_rejected(client, user_row):
    client.post("/auth/register", data={"username": "bob", "password": "x" * 1025})
    assert user_row("bob") is None


# --- Logout ------------------------------------------------------------------

def test_get_logout_only_asks(client, alice):
    _login(client)
    resp = client.get("/auth/logout")
    assert resp.status_code == 200
    assert b"Log out?" in resp.data
    assert _logged_in(client)


def test_post_logout_logs_out(client, alice):
    _login(client)
    assert client.post("/auth/logout").status_code == 302
    assert not _logged_in(client)


def test_forged_logout_is_rejected(client, alice):
    _login(client)
    assert client.post("/auth/logout", csrf=False).status_code == 400
    assert _logged_in(client)


def test_nav_logout_is_a_form(client, alice):
    _login(client)
    html = client.get("/widgets").get_data(as_text=True)
    assert 'action="/auth/logout"' in html
    assert 'href="/auth/logout"' not in html


# --- Notification time zone --------------------------------------------------

def test_notification_times_use_app_timezone(app, client, auth, notifications):
    app.config["APP_TZINFO"] = ZoneInfo("America/Chicago")
    auth.register("alice", GOOD, email="alice@example.com")
    wid = client.post("/api/widgets", json={"name": "Room A"}).get_json()["id"]
    client.post(f"/api/widgets/{wid}/reservations",
                json={"start_time": "2026-06-01T14:00Z", "end_time": "2026-06-01T15:30Z"})
    body = notifications()[-1]["body"]
    assert "When: Mon, Jun 1, 2026, 9:00 AM – 10:30 AM CDT" in body


def test_invalid_app_timezone_fails_fast():
    fd, path = tempfile.mkstemp(suffix=".sqlite")
    try:
        with pytest.raises(RuntimeError, match="not a known time zone"):
            create_app({"TESTING": True, "DATABASE": path, "SECRET_KEY": "t",
                        "APP_TIMEZONE": "Mars/Olympus_Mons"})
    finally:
        os.close(fd)
        os.unlink(path)
