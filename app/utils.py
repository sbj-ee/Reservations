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
