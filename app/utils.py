from datetime import datetime

# Canonical storage format. Minute precision keeps comparisons simple, and the
# fixed width means lexicographic string ordering matches chronological order,
# which is what the overlap query in models.py relies on.
DT_FORMAT = "%Y-%m-%d %H:%M"

# Accepted input shapes (HTML datetime-local sends the 'T' variant).
_INPUT_FORMATS = (
    "%Y-%m-%d %H:%M",
    "%Y-%m-%dT%H:%M",
    "%Y-%m-%d %H:%M:%S",
    "%Y-%m-%dT%H:%M:%S",
)


def parse_dt(value):
    """Parse a user-supplied datetime string into a canonical 'YYYY-MM-DD HH:MM' string.

    Raises ValueError if the value is empty or not a recognized datetime.
    """
    if not value or not value.strip():
        raise ValueError("datetime is required")
    value = value.strip()
    for fmt in _INPUT_FORMATS:
        try:
            return datetime.strptime(value, fmt).strftime(DT_FORMAT)
        except ValueError:
            continue
    raise ValueError(f"invalid datetime: {value!r}")
