from werkzeug.security import generate_password_hash

from .db import get_db
from .utils import parse_dt


class OverlapError(Exception):
    """Raised when a reservation would overlap an existing one for the same widget."""


def unique_violation_message(exc):
    """Map a SQLite UNIQUE-constraint error to a friendly, field-specific message."""
    msg = str(exc).lower()
    if "user.email" in msg:
        return "that email is already in use"
    if "user.phone" in msg:
        return "that phone number is already in use"
    if "user.username" in msg:
        return "that username is already taken"
    return "that username, email, or phone is already in use"


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


def _has_overlap(db, widget_id, start, end, exclude_id=None):
    # Two intervals overlap iff existing.start < new.end AND new.start < existing.end.
    sql = (
        "SELECT 1 FROM reservation "
        "WHERE widget_id = ? AND start_time < ? AND ? < end_time"
    )
    params = [widget_id, end, start]
    if exclude_id is not None:
        sql += " AND id != ?"
        params.append(exclude_id)
    return db.execute(sql + " LIMIT 1", params).fetchone() is not None


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
    if _has_overlap(db, widget_id, start, end):
        raise OverlapError("widget is already reserved for that time range")

    cur = db.execute(
        """INSERT INTO reservation (widget_id, user_id, start_time, end_time, note)
           VALUES (?, ?, ?, ?, ?)""",
        (widget_id, user_id, start, end, (note or "").strip()),
    )
    db.commit()
    return cur.lastrowid


def update_reservation(reservation_id, start_time, end_time, note=""):
    """Change a reservation's time range / note, rejecting overlaps with others.

    Raises ValueError for bad input and OverlapError on a time conflict.
    """
    reservation = get_reservation(reservation_id)
    if reservation is None:
        raise ValueError("reservation not found")

    start = parse_dt(start_time)
    end = parse_dt(end_time)
    if end <= start:
        raise ValueError("end time must be after start time")

    db = get_db()
    if _has_overlap(db, reservation["widget_id"], start, end, exclude_id=reservation_id):
        raise OverlapError("widget is already reserved for that time range")

    db.execute(
        "UPDATE reservation SET start_time = ?, end_time = ?, note = ? WHERE id = ?",
        (start, end, (note or "").strip(), reservation_id),
    )
    db.commit()


def delete_reservation(reservation_id):
    db = get_db()
    db.execute("DELETE FROM reservation WHERE id = ?", (reservation_id,))
    db.commit()


def list_all_reservations():
    return query_reservations()


def query_reservations(date_from=None, date_to=None, widget_id=None, user_id=None):
    """All reservations (joined with widget + user), with optional filters.

    ``date_from`` / ``date_to`` are 'YYYY-MM-DD' dates filtered against start_time
    (inclusive). Invalid dates are ignored rather than raising.
    """
    sql = [
        """SELECT r.*, w.name AS widget_name, u.username
             FROM reservation r
             JOIN widget w ON w.id = r.widget_id
             JOIN user u ON u.id = r.user_id
            WHERE 1 = 1"""
    ]
    params = []
    if date_from and len((date_from or "").strip()) == 10:
        sql.append("AND r.start_time >= ?")
        params.append(date_from.strip() + " 00:00")
    if date_to and len((date_to or "").strip()) == 10:
        sql.append("AND r.start_time <= ?")
        params.append(date_to.strip() + " 23:59")
    if widget_id:
        sql.append("AND r.widget_id = ?")
        params.append(widget_id)
    if user_id:
        sql.append("AND r.user_id = ?")
        params.append(user_id)
    sql.append("ORDER BY r.start_time")
    return get_db().execute("\n".join(sql), params).fetchall()


def update_widget(widget_id, name, description):
    name = (name or "").strip()
    if not name:
        raise ValueError("name is required")
    db = get_db()
    db.execute(
        "UPDATE widget SET name = ?, description = ? WHERE id = ?",
        (name, (description or "").strip(), widget_id),
    )
    db.commit()


def delete_widget(widget_id):
    # reservation rows cascade via the ON DELETE CASCADE foreign key.
    db = get_db()
    db.execute("DELETE FROM widget WHERE id = ?", (widget_id,))
    db.commit()


# --- Users (admin) ---------------------------------------------------------

def get_user(user_id):
    db = get_db()
    return db.execute("SELECT * FROM user WHERE id = ?", (user_id,)).fetchone()


def list_users():
    db = get_db()
    return db.execute(
        """SELECT u.*, COUNT(r.id) AS reservation_count
             FROM user u
             LEFT JOIN reservation r ON r.user_id = u.id
         GROUP BY u.id
         ORDER BY u.username COLLATE NOCASE"""
    ).fetchall()


def set_user_admin(user_id, is_admin):
    db = get_db()
    db.execute(
        "UPDATE user SET is_admin = ? WHERE id = ?",
        (1 if is_admin else 0, user_id),
    )
    db.commit()


def create_user(username, password_hash, email=None, phone=None):
    """Insert a user. Raises ValueError on a blank or non-unique field."""
    username = (username or "").strip()
    if not username:
        raise ValueError("username is required")
    db = get_db()
    try:
        cur = db.execute(
            "INSERT INTO user (username, password_hash, email, phone) VALUES (?, ?, ?, ?)",
            (username, password_hash, (email or "").strip() or None, (phone or "").strip() or None),
        )
        db.commit()
        return cur.lastrowid
    except db.IntegrityError as e:
        raise ValueError(unique_violation_message(e))


def update_user_account(user_id, username, email, phone):
    """Admin edit of a user's username + contact info. Raises ValueError on a
    blank or non-unique field."""
    username = (username or "").strip()
    if not username:
        raise ValueError("username is required")
    db = get_db()
    try:
        db.execute(
            "UPDATE user SET username = ?, email = ?, phone = ? WHERE id = ?",
            (username, (email or "").strip() or None, (phone or "").strip() or None, user_id),
        )
        db.commit()
    except db.IntegrityError as e:
        raise ValueError(unique_violation_message(e))


def update_contact(user_id, email, phone):
    """Self-service update of a user's own email / phone. Raises ValueError if the
    email or phone is already used by another account."""
    db = get_db()
    try:
        db.execute(
            "UPDATE user SET email = ?, phone = ? WHERE id = ?",
            ((email or "").strip() or None, (phone or "").strip() or None, user_id),
        )
        db.commit()
    except db.IntegrityError as e:
        raise ValueError(unique_violation_message(e))


def set_password(user_id, raw_password):
    if not raw_password:
        raise ValueError("password is required")
    db = get_db()
    db.execute(
        "UPDATE user SET password_hash = ? WHERE id = ?",
        (generate_password_hash(raw_password), user_id),
    )
    db.commit()


def delete_user(user_id):
    """Delete a user, their reservations, and detach any widgets they created."""
    db = get_db()
    db.execute("DELETE FROM reservation WHERE user_id = ?", (user_id,))
    db.execute("UPDATE widget SET created_by = NULL WHERE created_by = ?", (user_id,))
    db.execute("DELETE FROM user WHERE id = ?", (user_id,))
    db.commit()


def counts():
    db = get_db()
    return {
        "users": db.execute("SELECT COUNT(*) AS n FROM user").fetchone()["n"],
        "widgets": db.execute("SELECT COUNT(*) AS n FROM widget").fetchone()["n"],
        "reservations": db.execute("SELECT COUNT(*) AS n FROM reservation").fetchone()["n"],
        "notifications": db.execute("SELECT COUNT(*) AS n FROM notification").fetchone()["n"],
    }


# --- Notifications ---------------------------------------------------------

def reservation_snapshot(reservation_id):
    """A reservation joined with its widget name and the owner's contact info.

    Used to build notification messages; capture it before deleting a reservation.
    """
    db = get_db()
    return db.execute(
        """SELECT r.*, w.name AS widget_name,
                  u.username, u.email, u.phone
             FROM reservation r
             JOIN widget w ON w.id = r.widget_id
             JOIN user u ON u.id = r.user_id
            WHERE r.id = ?""",
        (reservation_id,),
    ).fetchone()


def record_notification(
    reservation_id, user_id, event, channel, recipient, subject, body, status, detail=""
):
    db = get_db()
    db.execute(
        """INSERT INTO notification
             (reservation_id, user_id, event, channel, recipient, subject, body, status, detail)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (reservation_id, user_id, event, channel, recipient, subject, body, status, detail),
    )
    db.commit()


def list_notifications(limit=100):
    db = get_db()
    return db.execute(
        "SELECT * FROM notification ORDER BY id DESC LIMIT ?", (limit,)
    ).fetchall()


# --- Password reset --------------------------------------------------------

def find_user_by_identifier(identifier):
    """Find a user by username or email (for password reset requests)."""
    identifier = (identifier or "").strip()
    if not identifier:
        return None
    db = get_db()
    return db.execute(
        "SELECT * FROM user WHERE username = ? OR email = ?", (identifier, identifier)
    ).fetchone()


def create_password_reset(user_id, token_hash, expires_at):
    """Store a reset token (hashed), replacing any unused ones for the user."""
    db = get_db()
    db.execute("DELETE FROM password_reset WHERE user_id = ? AND used = 0", (user_id,))
    db.execute(
        "INSERT INTO password_reset (user_id, token_hash, expires_at) VALUES (?, ?, ?)",
        (user_id, token_hash, expires_at),
    )
    db.commit()


def get_password_reset(token_hash):
    db = get_db()
    return db.execute(
        "SELECT * FROM password_reset WHERE token_hash = ?", (token_hash,)
    ).fetchone()


def mark_reset_used(reset_id):
    db = get_db()
    db.execute("UPDATE password_reset SET used = 1 WHERE id = ?", (reset_id,))
    db.commit()
