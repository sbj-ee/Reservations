"""Overlap prevention must hold across concurrent requests (separate gunicorn
workers = separate SQLite connections), not just sequential ones."""
import threading
import time

import pytest

from app import models
from app.db import get_db


@pytest.fixture
def widget_and_users(app):
    with app.app_context():
        db = get_db()
        ids = []
        for name in ("alice", "bob"):
            ids.append(
                db.execute(
                    "INSERT INTO user (username, password_hash) VALUES (?, 'x')", (name,)
                ).lastrowid
            )
        widget_id = db.execute(
            "INSERT INTO widget (name, created_by) VALUES ('Room A', ?)", (ids[0],)
        ).lastrowid
        db.commit()
    return widget_id, ids


def _race(app, monkeypatch, attempts):
    """Run each attempt in its own thread/connection, with a pause between the
    overlap check and the write so unsynchronized check-then-write would interleave."""
    real_check = models._has_overlap

    def slow_check(*args, **kwargs):
        result = real_check(*args, **kwargs)
        time.sleep(0.3)
        return result

    monkeypatch.setattr(models, "_has_overlap", slow_check)

    outcomes = []
    lock = threading.Lock()

    def worker(fn):
        with app.app_context():
            try:
                fn()
                outcome = "ok"
            except models.OverlapError:
                outcome = "overlap"
        with lock:
            outcomes.append(outcome)

    threads = [threading.Thread(target=worker, args=(fn,)) for fn in attempts]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)
    return sorted(outcomes)


def _count(app, widget_id):
    with app.app_context():
        return get_db().execute(
            "SELECT COUNT(*) FROM reservation WHERE widget_id = ?", (widget_id,)
        ).fetchone()[0]


def test_concurrent_overlapping_creates_book_only_once(app, monkeypatch, widget_and_users):
    widget_id, (alice, bob) = widget_and_users
    outcomes = _race(app, monkeypatch, [
        lambda: models.create_reservation(widget_id, alice, "2026-06-01T09:00", "2026-06-01T10:00"),
        lambda: models.create_reservation(widget_id, bob, "2026-06-01T09:30", "2026-06-01T10:30"),
    ])
    assert outcomes == ["ok", "overlap"]
    assert _count(app, widget_id) == 1


def test_concurrent_update_and_create_cannot_overlap(app, monkeypatch, widget_and_users):
    widget_id, (alice, bob) = widget_and_users
    with app.app_context():
        rid = models.create_reservation(widget_id, alice, "2026-06-01T07:00", "2026-06-01T08:00")
    outcomes = _race(app, monkeypatch, [
        lambda: models.update_reservation(rid, "2026-06-01T09:00", "2026-06-01T10:00"),
        lambda: models.create_reservation(widget_id, bob, "2026-06-01T09:30", "2026-06-01T10:30"),
    ])
    assert outcomes == ["ok", "overlap"]
