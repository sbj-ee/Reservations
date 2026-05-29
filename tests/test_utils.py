import pytest

from app.utils import parse_dt


def test_naive_input_is_treated_as_utc():
    assert parse_dt("2026-06-01T09:00") == "2026-06-01 09:00"
    assert parse_dt("2026-06-01 09:00") == "2026-06-01 09:00"


def test_z_designator_is_utc():
    assert parse_dt("2026-06-01T09:00Z") == "2026-06-01 09:00"


def test_offset_is_converted_to_utc():
    # 09:00 at UTC-5 is 14:00 UTC
    assert parse_dt("2026-06-01T09:00-05:00") == "2026-06-01 14:00"
    # 09:00 at UTC+2 is 07:00 UTC
    assert parse_dt("2026-06-01T09:00+02:00") == "2026-06-01 07:00"


def test_offset_can_roll_over_date():
    # 23:30 at UTC-5 is 04:30 the next day in UTC
    assert parse_dt("2026-06-01T23:30-05:00") == "2026-06-02 04:30"


def test_seconds_are_truncated_to_minutes():
    assert parse_dt("2026-06-01T09:00:45+00:00") == "2026-06-01 09:00"


def test_blank_and_invalid_raise():
    with pytest.raises(ValueError):
        parse_dt("")
    with pytest.raises(ValueError):
        parse_dt("not-a-date")
