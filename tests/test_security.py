import pytest


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
