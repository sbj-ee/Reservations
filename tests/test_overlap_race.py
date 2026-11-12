"""The overlap check and the write must be atomic.

Simulates another worker process booking the same slot in the window between our
overlap check and our INSERT/UPDATE. With the check and write in one
write-locked transaction, the other writer is blocked and only one booking
survives.
"""

import sqlite3

import pytest

from app import models

SLOT = ("2030-01-01 10:00", "2030-01-01 11:00")


def _setup(app):
    user_id = models.create_user("alice", "x")
    widget_id = models.create_widget("Room A", "", user_id)
    return user_id, widget_id


def _install_racing_writer(app, monkeypatch, widget_id, user_id):
    """Patch _has_overlap so a second connection tries to book SLOT right after
    the check returns. Records whether that writer got in or was blocked."""
    outcome = {}
    real = models._has_overlap

    def racing(db, *args, **kwargs):
        result = real(db, *args, **kwargs)
        other = sqlite3.connect(app.config["DATABASE"], timeout=0)
        try:
            other.execute(
                "INSERT INTO reservation (widget_id, user_id, start_time, end_time)"
                " VALUES (?, ?, ?, ?)",
                (widget_id, user_id, *SLOT),
            )
            other.commit()
            outcome["intruder"] = "inserted"
        except sqlite3.OperationalError:
            outcome["intruder"] = "blocked"
        finally:
            other.close()
        return result

    monkeypatch.setattr(models, "_has_overlap", racing)
    return outcome


def _overlapping_count(widget_id):
    from app.db import get_db

    return get_db().execute(
        "SELECT COUNT(*) FROM reservation"
        " WHERE widget_id = ? AND start_time < ? AND ? < end_time",
        (widget_id, SLOT[1], SLOT[0]),
    ).fetchone()[0]


def test_create_is_atomic_with_overlap_check(app, monkeypatch):
    with app.app_context():
        user_id, widget_id = _setup(app)
        outcome = _install_racing_writer(app, monkeypatch, widget_id, user_id)

        models.create_reservation(widget_id, user_id, *SLOT)

        assert outcome["intruder"] == "blocked"
        assert _overlapping_count(widget_id) == 1


def test_update_is_atomic_with_overlap_check(app, monkeypatch):
    with app.app_context():
        user_id, widget_id = _setup(app)
        rid = models.create_reservation(
            widget_id, user_id, "2030-01-01 08:00", "2030-01-01 09:00"
        )
        outcome = _install_racing_writer(app, monkeypatch, widget_id, user_id)

        models.update_reservation(rid, *SLOT)

        assert outcome["intruder"] == "blocked"
        assert _overlapping_count(widget_id) == 1


def test_overlap_error_releases_lock(app):
    with app.app_context():
        user_id, widget_id = _setup(app)
        models.create_reservation(widget_id, user_id, *SLOT)
        with pytest.raises(models.OverlapError):
            models.create_reservation(widget_id, user_id, *SLOT)
        # The failed attempt must not leave a transaction (and write lock) open.
        from app.db import get_db

        assert not get_db().in_transaction
        other = sqlite3.connect(app.config["DATABASE"], timeout=0)
        other.execute("UPDATE widget SET name = name")
        other.commit()
        other.close()
