def test_account_requires_login(client):
    resp = client.get("/account")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_update_contact_details(client, auth, user_row):
    auth.register()
    resp = client.post(
        "/account",
        data={"action": "profile", "email": "alice@example.com", "phone": "+15551230001"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    row = user_row("alice")
    assert row["email"] == "alice@example.com"
    assert row["phone"] == "+15551230001"


def test_clearing_contact_sets_null(client, auth, user_row):
    auth.register(email="alice@example.com", phone="+15551230001")
    client.post("/account", data={"action": "profile", "email": "", "phone": ""})
    row = user_row("alice")
    assert row["email"] is None
    assert row["phone"] is None


def test_change_password_success(client, auth):
    auth.register(password="oldpw")
    resp = client.post(
        "/account",
        data={
            "action": "password",
            "current_password": "oldpw",
            "new_password": "newpw",
            "confirm_password": "newpw",
        },
        follow_redirects=True,
    )
    assert b"Password changed." in resp.data
    auth.logout()
    assert auth.login(password="newpw").status_code == 302  # new works
    auth.logout()
    assert b"Incorrect" in auth.login(password="oldpw").data  # old rejected


def test_change_password_wrong_current(client, auth):
    auth.register(password="oldpw")
    resp = client.post(
        "/account",
        data={
            "action": "password",
            "current_password": "WRONG",
            "new_password": "newpw",
            "confirm_password": "newpw",
        },
    )
    assert b"Current password is incorrect." in resp.data
    # Password unchanged: old still works.
    auth.logout()
    assert auth.login(password="oldpw").status_code == 302


def test_change_password_mismatch(client, auth):
    auth.register(password="oldpw")
    resp = client.post(
        "/account",
        data={
            "action": "password",
            "current_password": "oldpw",
            "new_password": "newpw",
            "confirm_password": "different",
        },
    )
    assert b"New passwords do not match." in resp.data
