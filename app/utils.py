from datetime import datetime, timezone

# Canonical storage format — all reservation times are stored in UTC.
# Minute precision keeps comparisons simple, and the fixed width means
# lexicographic string ordering matches chronological order, which is what the
# overlap query in models.py relies on. Storing UTC means an overlap is detected
# correctly even when the two bookings were entered in different time zones.
DT_FORMAT = "%Y-%m-%d %H:%M"

# Fallback shapes for naive (no time zone) input.
_INPUT_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def parse_dt(value):
    """Parse a user-supplied datetime into a canonical UTC 'YYYY-MM-DD HH:MM' string.

    Time-zone-aware input (ISO 8601 with an offset or a trailing 'Z') is converted
    to UTC. Naive input — what the web UI submits after converting to UTC in the
    browser, and what API clients send when already in UTC — is assumed to be UTC.

    Raises ValueError if the value is empty or not a recognized datetime.
    """
    if not value or not value.strip():
        raise ValueError("datetime is required")
    value = value.strip()

    dt = None
    try:
        # Handles 'T'/' ' separators, optional seconds, offsets, and 'Z' (Py 3.11+).
        dt = datetime.fromisoformat(value)
    except ValueError:
        for fmt in _INPUT_FORMATS:
            try:
                dt = datetime.strptime(value, fmt)
                break
            except ValueError:
                continue
    if dt is None:
        raise ValueError(f"invalid datetime: {value!r}")

    if dt.tzinfo is not None:
        dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
    return dt.strftime(DT_FORMAT)


def system_timezone_name():
    """Best-effort IANA name of the server's own time zone (e.g. 'America/Chicago'),
    used when APP_TIMEZONE isn't set. Falls back to 'UTC'."""
    import os

    tz = os.environ.get("TZ", "").lstrip(":")
    if tz and "/" in tz:
        return tz
    try:
        with open("/etc/timezone") as f:
            name = f.read().strip()
            if name:
                return name
    except OSError:
        pass
    try:
        target = os.path.realpath("/etc/localtime")
        if "/zoneinfo/" in target:
            return target.split("/zoneinfo/", 1)[1]
    except OSError:
        pass
    return "UTC"


def _fmt_12h(dt):
    return f"{(dt.hour % 12) or 12}:{dt.minute:02d} {'AM' if dt.hour < 12 else 'PM'}"


def format_utc_range(start, end, tz):
    """Format stored UTC 'YYYY-MM-DD HH:MM' start/end for people, in zone ``tz``
    (a ZoneInfo), naming the zone, e.g.
    'Sat, Nov 14, 2026, 10:30 AM – 12:00 PM CST' (same day) or
    'Sat, Nov 14, 2026, 10:30 PM CST – Sun, Nov 15, 2026, 1:00 AM CST'."""
    a = datetime.strptime(start, DT_FORMAT).replace(tzinfo=timezone.utc).astimezone(tz)
    b = datetime.strptime(end, DT_FORMAT).replace(tzinfo=timezone.utc).astimezone(tz)

    def day(d):
        return f"{d:%a}, {d:%b} {d.day}, {d.year}"

    if a.date() == b.date() and a.tzname() == b.tzname():
        return f"{day(a)}, {_fmt_12h(a)} – {_fmt_12h(b)} {b.tzname()}"
    return f"{day(a)}, {_fmt_12h(a)} {a.tzname()} – {day(b)}, {_fmt_12h(b)} {b.tzname()}"
