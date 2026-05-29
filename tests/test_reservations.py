from tests.conftest import basic_auth_header


def _make_widget(client, auth):
    auth.register()
    resp = client.post("/api/widgets", json={"name": "Room A"})
    return resp.get_json()["id"]


def test_create_reservation_success(client, auth):
    widget_id = _make_widget(client, auth)
    resp = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"},
    )
    assert resp.status_code == 201
    body = resp.get_json()
    assert body["start_time"] == "2026-06-01 09:00"
    assert body["end_time"] == "2026-06-01 10:00"


def test_overlapping_reservation_rejected(client, auth):
    widget_id = _make_widget(client, auth)
    base = {"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"}
    assert client.post(f"/api/widgets/{widget_id}/reservations", json=base).status_code == 201
    # Overlaps the first booking.
    resp = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:30", "end_time": "2026-06-01T10:30"},
    )
    assert resp.status_code == 409


def test_adjacent_reservation_allowed(client, auth):
    widget_id = _make_widget(client, auth)
    assert client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"},
    ).status_code == 201
    # Starts exactly when the previous one ends -> no overlap.
    resp = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T10:00", "end_time": "2026-06-01T11:00"},
    )
    assert resp.status_code == 201


def test_cross_timezone_overlap_detected(client, auth):
    """Two bookings entered in different time zones for the same real instant
    must conflict because both are stored in UTC."""
    widget_id = _make_widget(client, auth)
    # 09:00-10:00 at UTC-5  ==  14:00-15:00 UTC
    assert client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00-05:00", "end_time": "2026-06-01T10:00-05:00"},
    ).status_code == 201
    # Someone in UTC tries 14:30-15:30 UTC — overlaps the first booking.
    assert client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T14:30Z", "end_time": "2026-06-01T15:30Z"},
    ).status_code == 409


def test_stored_time_is_utc(client, auth):
    widget_id = _make_widget(client, auth)
    res = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00-05:00", "end_time": "2026-06-01T10:00-05:00"},
    ).get_json()
    assert res["start_time"] == "2026-06-01 14:00"
    assert res["end_time"] == "2026-06-01 15:00"


def test_end_before_start_rejected(client, auth):
    widget_id = _make_widget(client, auth)
    resp = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T10:00", "end_time": "2026-06-01T09:00"},
    )
    assert resp.status_code == 400


def test_reservation_requires_auth(client, auth):
    widget_id = _make_widget(client, auth)
    auth.logout()
    resp = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"},
    )
    assert resp.status_code == 401


def test_cancel_reservation(client, auth):
    widget_id = _make_widget(client, auth)
    created = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"},
    ).get_json()
    resp = client.delete(f"/api/reservations/{created['id']}")
    assert resp.status_code == 204
    assert client.get("/api/reservations").get_json() == []


def test_cannot_cancel_another_users_reservation(client, auth):
    widget_id = _make_widget(client, auth)
    created = client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"},
    ).get_json()
    auth.logout()
    auth.register(username="bob", password="secret")
    resp = client.delete(f"/api/reservations/{created['id']}")
    assert resp.status_code == 403


def test_ui_overlap_shows_flash(client, auth):
    widget_id = _make_widget(client, auth)
    client.post(
        f"/widgets/{widget_id}/reserve",
        data={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00"},
    )
    resp = client.post(
        f"/widgets/{widget_id}/reserve",
        data={"start_time": "2026-06-01T09:30", "end_time": "2026-06-01T11:00"},
        follow_redirects=True,
    )
    assert b"already reserved" in resp.data
