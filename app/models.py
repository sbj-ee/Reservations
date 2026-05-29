from .db import get_db
from .utils import parse_dt


class OverlapError(Exception):
    """Raised when a reservation would overlap an existing one for the same widget."""


# --- Widgets ---------------------------------------------------------------

def list_widgets():
    db = get_db()
    return db.execute(
        "SELECT * FROM widget ORDER BY name COLLATE NOCASE"
    ).fetchall()


def get_widget(widget_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM widget WHERE id = ?", (widget_id,)
    ).fetchone()


def create_widget(name, description, created_by):
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    db = get_db()
    cur = db.execute(
        "INSERT INTO widget (name, description, created_by) VALUES (?, ?, ?)",
        (name, (description or "").strip(), created_by),
    )
    db.commit()
    return cur.lastrowid


# --- Reservations ----------------------------------------------------------

def list_reservations_for_widget(widget_id):
    db = get_db()
    return db.execute(
        """SELECT r.*, u.username
             FROM reservation r JOIN user u ON u.id = r.user_id
            WHERE r.widget_id = ?
         ORDER BY r.start_time""",
        (widget_id,),
    ).fetchall()


def list_reservations_for_user(user_id):
    db = get_db()
    return db.execute(
        """SELECT r.*, w.name AS widget_name
             FROM reservation r JOIN widget w ON w.id = r.widget_id
            WHERE r.user_id = ?
         ORDER BY r.start_time""",
        (user_id,),
    ).fetchall()


def get_reservation(reservation_id):
    db = get_db()
    return db.execute(
        "SELECT * FROM reservation WHERE id = ?", (reservation_id,)
    ).fetchone()


def create_reservation(widget_id, user_id, start_time, end_time, note=""):
    """Create a reservation, rejecting overlaps for the same widget.

    Raises ValueError for bad input and OverlapError on a time conflict.
    """
    if get_widget(widget_id) is None:
        raise ValueError("widget not found")

    start = parse_dt(start_time)
    end = parse_dt(end_time)
    if end <= start:
        raise ValueError("end time must be after start time")

    db = get_db()
    # Two intervals overlap iff existing.start < new.end AND new.start < existing.end.
    conflict = db.execute(
        """SELECT 1 FROM reservation
            WHERE widget_id = ? AND start_time < ? AND ? < end_time
            LIMIT 1""",
        (widget_id, end, start),
    ).fetchone()
    if conflict is not None:
        raise OverlapError("widget is already reserved for that time range")

    cur = db.execute(
        """INSERT INTO reservation (widget_id, user_id, start_time, end_time, note)
           VALUES (?, ?, ?, ?, ?)""",
        (widget_id, user_id, start, end, (note or "").strip()),
    )
    db.commit()
    return cur.lastrowid


def delete_reservation(reservation_id):
    db = get_db()
    db.execute("DELETE FROM reservation WHERE id = ?", (reservation_id,))
    db.commit()
