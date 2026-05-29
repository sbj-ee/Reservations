def test_register_logs_in_and_redirects(client, auth):
    resp = auth.register()
    assert resp.status_code == 302
    # Now authenticated: visiting login redirects away.
    assert client.get("/auth/login").status_code == 302


def test_duplicate_registration_shows_error(client, auth):
    auth.register()
    auth.logout()
    resp = auth.register()  # same username again
    assert b"already registered" in resp.data


def test_login_with_bad_password(client, auth):
    auth.register()
    auth.logout()
    resp = auth.login(password="wrong")
    assert b"Incorrect username or password." in resp.data


def test_login_required_redirects_anonymous(client):
    resp = client.get("/widgets/new")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]
