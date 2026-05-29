import hashlib
import re

from app import models


def _reset_token(notifications):
    rows = [n for n in notifications() if n["event"] == "password_reset"]
    assert rows, "no password_reset notification was recorded"
    m = re.search(r"/auth/reset/([A-Za-z0-9_-]+)", rows[-1]["body"])
    assert m, f"no reset link found in body: {rows[-1]['body']!r}"
    return m.group(1)


def test_forgot_page_renders(client):
    assert client.get("/auth/forgot").status_code == 200


def test_forgot_unknown_user_is_enumeration_safe(client, auth, notifications):
    resp = client.post(
        "/auth/forgot", data={"identifier": "nobody"}, follow_redirects=True
    )
    assert b"If an account matches" in resp.data
    assert [n for n in notifications() if n["event"] == "password_reset"] == []


def test_forgot_user_without_email_records_nothing(client, auth, notifications):
    auth.register(username="alice")  # no email on file
    auth.logout()
    resp = client.post(
        "/auth/forgot", data={"identifier": "alice"}, follow_redirects=True
    )
    assert b"If an account matches" in resp.data
    assert [n for n in notifications() if n["event"] == "password_reset"] == []


def test_forgot_records_reset_email(client, auth, notifications):
    auth.register(username="alice", email="alice@example.com")
    auth.logout()
    client.post("/auth/forgot", data={"identifier": "alice@example.com"})
    rows = [n for n in notifications() if n["event"] == "password_reset"]
    assert len(rows) == 1
    assert rows[0]["channel"] == "email"
    assert rows[0]["recipient"] == "alice@example.com"
    assert rows[0]["status"] == "logged"  # no provider configured in tests


def test_full_reset_flow(client, auth, notifications):
    auth.register(username="alice", password="oldpw", email="alice@example.com")
    auth.logout()
    client.post("/auth/forgot", data={"identifier": "alice"})
    token = _reset_token(notifications)

    assert client.get(f"/auth/reset/{token}").status_code == 200
    resp = client.post(
        f"/auth/reset/{token}",
        data={"new_password": "newpw", "confirm_password": "newpw"},
        follow_redirects=True,
    )
    assert b"has been reset" in resp.data
    # New password works; old does not.
    assert auth.login(username="alice", password="newpw").status_code == 302
    auth.logout()
    assert b"Incorrect" in auth.login(username="alice", password="oldpw").data


def test_token_is_single_use(client, auth, notifications):
    auth.register(username="alice", password="oldpw", email="alice@example.com")
    auth.logout()
    client.post("/auth/forgot", data={"identifier": "alice"})
    token = _reset_token(notifications)
    client.post(
        f"/auth/reset/{token}",
        data={"new_password": "newpw", "confirm_password": "newpw"},
    )
    resp = client.get(f"/auth/reset/{token}", follow_redirects=True)
    assert b"invalid or has expired" in resp.data


def test_invalid_token_rejected(client):
    resp = client.get("/auth/reset/nope-not-real", follow_redirects=True)
    assert b"invalid or has expired" in resp.data


def test_expired_token_rejected(app, client, auth, user_row):
    auth.register(username="alice", email="alice@example.com")
    uid = user_row("alice")["id"]
    token = "expired-token-value"
    with app.app_context():
        models.create_password_reset(
            uid, hashlib.sha256(token.encode()).hexdigest(), "2000-01-01 00:00:00"
        )
    resp = client.get(f"/auth/reset/{token}", follow_redirects=True)
    assert b"invalid or has expired" in resp.data


def test_reset_password_mismatch(client, auth, notifications):
    auth.register(username="alice", email="alice@example.com")
    auth.logout()
    client.post("/auth/forgot", data={"identifier": "alice"})
    token = _reset_token(notifications)
    resp = client.post(
        f"/auth/reset/{token}",
        data={"new_password": "aaa", "confirm_password": "bbb"},
    )
    assert b"do not match" in resp.data
