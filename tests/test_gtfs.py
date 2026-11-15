from datetime import date
from pathlib import Path

import pytest

from transfergap.gtfs import FeedError, format_gtfs_time, load_stop_times, parse_gtfs_time

DATA = Path(__file__).parents[1] / "data" / "sample" / "gtfs"


def test_gtfs_time_supports_after_midnight_service_hours():
    assert parse_gtfs_time("25:10:05", field="time") == 90_605
    assert format_gtfs_time(90_605) == "25:10:05"


@pytest.mark.parametrize("value", ["8:00", "08:60:00", "08:00:60", "x:00:00"])
def test_invalid_gtfs_times_are_rejected(value):
    with pytest.raises(FeedError):
        parse_gtfs_time(value, field="time")


def test_only_active_service_trips_are_loaded():
    stops = load_stop_times(DATA, date(2026, 10, 5))
    assert {row.trip_id for row in stops} == {
        "R1_IN_0800",
        "R1_IN_0830",
        "R2_OUT_0817",
        "R2_OUT_0847",
        "R3_OUT_0825",
    }


def test_inactive_service_date_fails_explicitly():
    with pytest.raises(FeedError, match="No active GTFS services"):
        load_stop_times(DATA, date(2026, 10, 3))
