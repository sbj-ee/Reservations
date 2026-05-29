from tests.conftest import basic_auth_header


def test_create_widget_via_ui(client, auth):
    auth.register()
    resp = client.post(
        "/widgets/new",
        data={"name": "Drill", "description": "A power tool"},
        follow_redirects=True,
    )
    assert b"Drill" in resp.data
    # Appears on the public list page.
    assert b"Drill" in client.get("/widgets").data


def test_api_list_widgets_is_public(client):
    assert client.get("/api/widgets").get_json() == []


def test_api_create_widget_requires_auth(client):
    resp = client.post("/api/widgets", json={"name": "X"})
    assert resp.status_code == 401


def test_api_create_widget_with_basic_auth(client, auth):
    auth.register()
    auth.logout()  # drop the session so only Basic auth is in play
    resp = client.post(
        "/api/widgets",
        json={"name": "Saw", "description": "cuts things"},
        headers=basic_auth_header(),
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["name"] == "Saw"
    assert body["id"] > 0


def test_api_create_widget_rejects_blank_name(client, auth):
    auth.register()
    resp = client.post("/api/widgets", json={"name": "  "})
    assert resp.status_code == 400
