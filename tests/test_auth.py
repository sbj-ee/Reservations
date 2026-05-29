def test_register_logs_in_and_redirects(client, auth):
    resp = auth.register()
    assert resp.status_code == 302
    # Now authenticated: visiting login redirects away.
    assert client.get("/auth/login").status_code == 302


def test_duplicate_registration_shows_error(client, auth):
    auth.register()
    auth.logout()
    resp = auth.register()  # same username again
    assert b"already taken" in resp.data


def test_login_with_bad_password(client, auth):
    auth.register()
    auth.logout()
    resp = auth.login(password="wrong")
    assert b"Incorrect username or password." in resp.data


def test_login_required_redirects_anonymous(client):
    resp = client.get("/widgets/new")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_register_duplicate_email_rejected(client, auth):
    auth.register(username="alice", email="dup@example.com")
    auth.logout()
    resp = auth.register(username="bob", email="dup@example.com")
    assert b"email is already in use" in resp.data


def test_register_duplicate_phone_rejected(client, auth):
    auth.register(username="alice", phone="+15550001111")
    auth.logout()
    resp = auth.register(username="bob", phone="+15550001111")
    assert b"phone number is already in use" in resp.data


def test_register_multiple_users_without_contact_ok(client, auth, user_row):
    auth.register(username="alice")  # no email/phone
    auth.logout()
    resp = auth.register(username="bob")  # also none -> NULLs are not "duplicates"
    assert resp.status_code == 302
    assert user_row("bob") is not None
