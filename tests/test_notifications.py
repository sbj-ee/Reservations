def _widget(client):
    return client.post("/api/widgets", json={"name": "Room A"}).get_json()["id"]


def _reserve(client, widget_id, start="2026-06-01T09:00", end="2026-06-01T10:00"):
    return client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": start, "end_time": end},
    ).get_json()


def test_create_notifies_owner_on_both_channels(client, auth, notifications):
    auth.register(email="alice@example.com", phone="+15551230001")
    _reserve(client, _widget(client))
    rows = notifications()
    channels = {r["channel"] for r in rows}
    assert channels == {"email", "sms"}
    assert all(r["event"] == "created" for r in rows)
    # No provider configured in tests -> messages are logged, still recorded.
    assert all(r["status"] == "logged" for r in rows)
    assert all("Room A" in r["subject"] for r in rows)


def test_no_contact_info_is_skipped(client, auth, notifications):
    auth.register()  # no email/phone
    _reserve(client, _widget(client))
    rows = notifications()
    assert len(rows) == 1
    assert rows[0]["channel"] == "none"
    assert rows[0]["status"] == "skipped"


def test_email_only_owner(client, auth, notifications):
    auth.register(email="alice@example.com")  # no phone
    _reserve(client, _widget(client))
    assert {r["channel"] for r in notifications()} == {"email"}


def test_update_notifies_with_updated_event(client, auth, notifications):
    auth.register(email="alice@example.com")
    res = _reserve(client, _widget(client))
    resp = client.put(
        f"/api/reservations/{res['id']}",
        json={"start_time": "2026-06-01T12:00", "end_time": "2026-06-01T13:00", "note": "moved"},
    )
    assert resp.status_code == 200
    events = [r["event"] for r in notifications()]
    assert events == ["created", "updated"]


def test_cancel_notifies_with_cancelled_event(client, auth, notifications):
    auth.register(email="alice@example.com")
    res = _reserve(client, _widget(client))
    assert client.delete(f"/api/reservations/{res['id']}").status_code == 204
    events = [r["event"] for r in notifications()]
    assert events[-1] == "cancelled"


def test_admin_delete_notifies_owner(client, auth, make_admin, notifications):
    auth.register(username="alice", email="alice@example.com")
    res = _reserve(client, _widget(client))
    make_admin("alice")
    client.post(f"/admin/reservations/{res['id']}/delete", follow_redirects=True)
    assert notifications()[-1]["event"] == "cancelled"


def test_booking_succeeds_even_if_notification_unconfigured(client, auth):
    auth.register(email="alice@example.com", phone="+15551230001")
    res = _reserve(client, _widget(client))
    # The reservation was created despite notifications only being logged.
    assert res["id"] > 0
    assert len(client.get("/api/reservations").get_json()) == 1


def test_email_send_failure_is_recorded_not_raised(app, client, auth, notifications):
    # Point email at a port with nothing listening: the send raises, but the
    # booking must still succeed and the failure is recorded.
    app.config.update(MAIL_SERVER="127.0.0.1", MAIL_PORT=9, MAIL_FROM="noreply@example.com")
    auth.register(email="alice@example.com")
    res = _reserve(client, _widget(client))
    assert res["id"] > 0
    email_rows = [r for r in notifications() if r["channel"] == "email"]
    assert email_rows[0]["status"] == "failed"
    assert email_rows[0]["detail"]


def test_update_overlap_rejected(client, auth):
    auth.register(email="alice@example.com")
    widget_id = _widget(client)
    a = _reserve(client, widget_id, "2026-06-01T09:00", "2026-06-01T10:00")
    b = _reserve(client, widget_id, "2026-06-01T11:00", "2026-06-01T12:00")
    # Try to move b on top of a.
    resp = client.put(
        f"/api/reservations/{b['id']}",
        json={"start_time": "2026-06-01T09:30", "end_time": "2026-06-01T09:45"},
    )
    assert resp.status_code == 409
