BANNER = b"your last login was"


def test_login_records_last_login(client, auth, user_row):
    auth.register(username="alice", password="pw")
    auth.logout()
    assert user_row("alice")["last_login_at"] is None  # registration isn't a login
    auth.login(username="alice", password="pw")
    assert user_row("alice")["last_login_at"] is not None


def test_first_login_shows_no_banner(client, auth):
    auth.register(username="alice", password="pw")
    auth.logout()
    auth.login(username="alice", password="pw")  # first login: no prior value
    assert BANNER not in client.get("/widgets").data


def test_second_login_shows_banner(client, auth):
    auth.register(username="alice", password="pw")
    auth.logout()
    auth.login(username="alice", password="pw")  # first login stamps last_login_at
    auth.logout()
    auth.login(username="alice", password="pw")  # second login -> prior value exists
    resp = client.get("/widgets", follow_redirects=True)
    assert BANNER in resp.data


def test_banner_is_one_time(client, auth):
    auth.register(username="alice", password="pw")
    auth.logout()
    auth.login(username="alice", password="pw")
    auth.logout()
    auth.login(username="alice", password="pw")  # second login sets the notice
    assert BANNER in client.get("/widgets").data       # shown once
    assert BANNER not in client.get("/widgets").data   # then cleared


def test_admin_users_shows_last_login_column(client, auth, make_admin):
    auth.register(username="alice")
    make_admin("alice")
    resp = client.get("/admin/users")
    assert b"Last login" in resp.data
