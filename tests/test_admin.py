def _make_widget_and_reservation(client, auth):
    auth.register()
    widget_id = client.post("/api/widgets", json={"name": "Room A"}).get_json()["id"]
    res = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"},
    ).get_json()
    return widget_id, res["id"]


def test_admin_requires_login(client):
    resp = client.get("/admin/")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_admin_forbidden_for_normal_user(client, auth):
    auth.register()  # normal user
    assert client.get("/admin/").status_code == 403
    assert client.get("/admin/users").status_code == 403


def test_admin_dashboard_for_admin(client, auth, make_admin):
    auth.register()
    make_admin("alice")
    resp = client.get("/admin/")
    assert resp.status_code == 200
    assert b"control panel" in resp.data


def test_admin_nav_link_visible_only_to_admin(client, auth, make_admin):
    auth.register()
    assert b"/admin/" not in client.get("/widgets").data
    make_admin("alice")
    assert b"/admin/" in client.get("/widgets").data


def test_admin_can_delete_any_reservation(client, auth, make_admin):
    _, reservation_id = _make_widget_and_reservation(client, auth)
    make_admin("alice")
    resp = client.post(
        f"/admin/reservations/{reservation_id}/delete", follow_redirects=True
    )
    assert resp.status_code == 200
    assert client.get("/api/reservations").get_json() == []


def test_admin_delete_widget_cascades_reservations(client, auth, make_admin):
    widget_id, _ = _make_widget_and_reservation(client, auth)
    make_admin("alice")
    client.post(f"/admin/widgets/{widget_id}/delete", follow_redirects=True)
    assert client.get("/api/widgets").get_json() == []
    # The reservation is gone with its widget.
    assert client.get("/api/reservations").get_json() == []


def test_admin_edit_widget(client, auth, make_admin):
    widget_id, _ = _make_widget_and_reservation(client, auth)
    make_admin("alice")
    client.post(
        f"/admin/widgets/{widget_id}/edit",
        data={"name": "Room A (renamed)", "description": "updated"},
        follow_redirects=True,
    )
    body = client.get(f"/api/widgets/{widget_id}").get_json()
    assert body["name"] == "Room A (renamed)"
    assert body["description"] == "updated"


def test_admin_toggle_another_users_admin(client, auth, make_admin, is_admin):
    auth.register(username="alice")
    make_admin("alice")
    auth.logout()
    auth.register(username="bob", password="secret")  # logs in as bob
    auth.logout()
    auth.login(username="alice")  # back to admin
    # alice=1, bob=2 by insertion order.
    resp = client.post("/admin/users/2/toggle-admin", follow_redirects=True)
    assert resp.status_code == 200
    assert is_admin("bob") is True


def test_admin_cannot_change_own_status(client, auth, make_admin, is_admin):
    auth.register()  # alice = user 1
    make_admin("alice")
    resp = client.post("/admin/users/1/toggle-admin", follow_redirects=True)
    assert b"cannot change your own admin status" in resp.data
    assert is_admin("alice") is True


def test_admin_cannot_delete_self(client, auth, make_admin):
    auth.register()  # alice = user 1
    make_admin("alice")
    resp = client.post("/admin/users/1/delete", follow_redirects=True)
    assert b"cannot delete your own account" in resp.data


def test_admin_edit_user_contact_and_username(client, auth, make_admin, user_row):
    auth.register(username="alice")  # user 1
    make_admin("alice")
    auth.logout()
    auth.register(username="bob", password="secret")  # user 2
    auth.logout()
    auth.login(username="alice")
    resp = client.post(
        "/admin/users/2/edit",
        data={"username": "bobby", "email": "bob@example.com", "phone": "+15550002222"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    row = user_row("bobby")
    assert row is not None
    assert row["email"] == "bob@example.com"
    assert row["phone"] == "+15550002222"
    assert user_row("bob") is None  # renamed


def test_admin_edit_user_duplicate_username_rejected(client, auth, make_admin, user_row):
    auth.register(username="alice")
    make_admin("alice")
    auth.logout()
    auth.register(username="bob", password="secret")
    auth.logout()
    auth.login(username="alice")
    resp = client.post(
        "/admin/users/2/edit", data={"username": "alice", "email": "", "phone": ""}
    )
    assert b"already taken" in resp.data
    assert user_row("bob") is not None  # unchanged


def test_admin_reset_user_password(client, auth, make_admin):
    auth.register(username="alice")
    make_admin("alice")
    auth.logout()
    auth.register(username="bob", password="secret")
    auth.logout()
    auth.login(username="alice")
    client.post(
        "/admin/users/2/edit",
        data={"username": "bob", "email": "", "phone": "", "new_password": "resetpw"},
        follow_redirects=True,
    )
    auth.logout()
    assert auth.login(username="bob", password="resetpw").status_code == 302
    auth.logout()
    assert b"Incorrect" in auth.login(username="bob", password="secret").data


def test_admin_edit_user_forbidden_for_normal_user(client, auth):
    auth.register()  # normal user
    assert client.get("/admin/users/1/edit").status_code == 403


def test_create_admin_cli(app):
    runner = app.test_cli_runner()
    result = runner.invoke(args=["create-admin", "root", "rootpw"])
    assert "Created admin" in result.output
    with app.app_context():
        from app.db import get_db
        row = get_db().execute(
            "SELECT is_admin FROM user WHERE username = 'root'"
        ).fetchone()
        assert row["is_admin"] == 1
