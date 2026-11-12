"""Throttling of failed password attempts.

Failures are recorded in SQLite (table ``login_failure``) so the limits hold across
all gunicorn workers. Three counters are checked, each over a sliding window:

* account + client IP: stops guessing one account from one place, without letting
  a stranger lock the real owner out from elsewhere;
* client IP: stops one client from spraying many accounts;
* account (any IP): a looser cap on distributed guessing against one account.

Only failures are counted. A successful login clears that account+IP counter.
``request.remote_addr`` is used as the client IP; if the app is ever put behind a
reverse proxy, configure werkzeug's ProxyFix so this is the real client address.
"""
from datetime import datetime, timedelta, timezone

from flask import current_app, request

from .db import get_db

_TS = "%Y-%m-%d %H:%M:%S"

DEFAULT_WINDOW_MINUTES = 15
DEFAULT_LIMITS = {"acct_ip": 5, "ip": 20, "acct": 50}


def _now():
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _window():
    return timedelta(
        minutes=current_app.config.get("LOGIN_WINDOW_MINUTES", DEFAULT_WINDOW_MINUTES)
    )


def _keys(username):
    account = (username or "").strip().lower()
    ip = request.remote_addr or "unknown"
    limits = {**DEFAULT_LIMITS, **current_app.config.get("LOGIN_LIMITS", {})}
    return [
        (f"acct_ip:{account}|{ip}", limits["acct_ip"]),
        (f"ip:{ip}", limits["ip"]),
        (f"acct:{account}", limits["acct"]),
    ]


def retry_after(username):
    """Seconds until another attempt is allowed for this username from this client,
    or 0 if not currently throttled."""
    db = get_db()
    now = _now()
    cutoff = (now - _window()).strftime(_TS)
    wait = 0
    for key, limit in _keys(username):
        rows = db.execute(
            "SELECT created_at FROM login_failure WHERE key = ? AND created_at > ? "
            "ORDER BY created_at DESC LIMIT ?",
            (key, cutoff, limit),
        ).fetchall()
        if len(rows) >= limit:
            # Allowed again once the oldest of the last `limit` failures ages out.
            oldest = datetime.strptime(rows[-1]["created_at"], _TS)
            wait = max(wait, int((oldest + _window() - now).total_seconds()) + 1)
    return wait


def record_failure(username):
    db = get_db()
    now = _now()
    db.executemany(
        "INSERT INTO login_failure (key, created_at) VALUES (?, ?)",
        [(key, now.strftime(_TS)) for key, _ in _keys(username)],
    )
    db.execute(
        "DELETE FROM login_failure WHERE created_at <= ?",
        ((now - _window()).strftime(_TS),),
    )
    db.commit()


def record_success(username):
    db = get_db()
    key = _keys(username)[0][0]
    # Check first: API clients using Basic auth succeed on every request, and an
    # unconditional DELETE would make each of those a database write.
    if db.execute("SELECT 1 FROM login_failure WHERE key = ? LIMIT 1", (key,)).fetchone():
        db.execute("DELETE FROM login_failure WHERE key = ?", (key,))
        db.commit()


def minutes(seconds):
    """Human-friendly wait, rounded up to whole minutes."""
    m = max(1, -(-seconds // 60))
    return f"{m} minute" + ("" if m == 1 else "s")
