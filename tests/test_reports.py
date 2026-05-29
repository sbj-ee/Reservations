def _seed(client, auth, make_admin):
    auth.register(username="alice")
    widget_id = client.post("/api/widgets", json={"name": "Room A"}).get_json()["id"]
    client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-06-01T09:00", "end_time": "2026-06-01T10:00", "note": "early"},
    )
    client.post(
        f"/api/widgets/{widget_id}/reservations",
        json={"start_time": "2026-07-15T09:00", "end_time": "2026-07-15T10:00", "note": "later"},
    )
    make_admin("alice")
    return widget_id


def test_csv_requires_login(client):
    resp = client.get("/admin/reports/reservations.csv")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_csv_forbidden_for_normal_user(client, auth):
    auth.register()  # normal user
    assert client.get("/admin/reports/reservations.csv").status_code == 403


def test_csv_export_contents(client, auth, make_admin):
    _seed(client, auth, make_admin)
    resp = client.get("/admin/reports/reservations.csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"
    assert "attachment; filename=reservations.csv" in resp.headers["Content-Disposition"]
    text = resp.get_data(as_text=True)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert lines[0].startswith("reservation_id,widget_id,widget,user")
    assert len(lines) == 3  # header + 2 reservations
    assert "Room A" in text and "alice" in text


def test_csv_widget_filter(client, auth, make_admin):
    _seed(client, auth, make_admin)  # creates widget "Room A" (id 1) with 2 reservations
    # add a second widget with one reservation
    other = client.post("/api/widgets", json={"name": "Room B"}).get_json()["id"]
    client.post(
        f"/api/widgets/{other}/reservations",
        json={"start_time": "2026-06-02T09:00", "end_time": "2026-06-02T10:00", "note": "B only"},
    )
    resp = client.get(f"/admin/reports/reservations.csv?widget_id={other}")
    text = resp.get_data(as_text=True)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 2  # header + only Room B's reservation
    assert "Room B" in text and "B only" in text
    assert "Room A" not in text


def test_csv_date_filter(client, auth, make_admin):
    _seed(client, auth, make_admin)
    resp = client.get("/admin/reports/reservations.csv?from=2026-07-01&to=2026-07-31")
    text = resp.get_data(as_text=True)
    lines = [ln for ln in text.splitlines() if ln.strip()]
    assert len(lines) == 2  # header + only the July reservation
    assert "later" in text
    assert "early" not in text
