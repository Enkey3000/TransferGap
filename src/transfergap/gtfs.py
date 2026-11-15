"""Small, dependency-free GTFS reader for scheduled-transfer analysis."""

from __future__ import annotations

import csv
from dataclasses import dataclass
from datetime import date
from pathlib import Path


class FeedError(ValueError):
    """Raised when a GTFS feed is missing required data or has invalid values."""


@dataclass(frozen=True)
class StopTime:
    trip_id: str
    route_id: str
    stop_id: str
    stop_name: str
    arrival_seconds: int | None
    departure_seconds: int | None
    stop_sequence: int


def parse_gtfs_time(value: str, *, field: str) -> int:
    """Parse GTFS HH:MM:SS, allowing hours beyond 23 as the specification does."""
    parts = value.strip().split(":")
    if len(parts) != 3:
        raise FeedError(f"{field} must use GTFS HH:MM:SS format; got {value!r}")
    try:
        hours, minutes, seconds = (int(part) for part in parts)
    except ValueError as exc:
        raise FeedError(f"{field} contains a non-integer time component: {value!r}") from exc
    if hours < 0 or not 0 <= minutes < 60 or not 0 <= seconds < 60:
        raise FeedError(f"{field} contains an out-of-range time: {value!r}")
    return hours * 3600 + minutes * 60 + seconds


def format_gtfs_time(total_seconds: int) -> str:
    """Format seconds since the service-day start as GTFS HH:MM:SS."""
    if total_seconds < 0:
        raise ValueError("total_seconds must be non-negative")
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}"


def _read_csv(path: Path, required: tuple[str, ...]) -> list[dict[str, str]]:
    if not path.is_file():
        raise FeedError(f"Required GTFS file not found: {path.name}")
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        missing = set(required) - set(reader.fieldnames or ())
        if missing:
            raise FeedError(f"{path.name} is missing required columns: {', '.join(sorted(missing))}")
        return list(reader)


def active_service_ids(feed_dir: Path, service_date: date) -> set[str]:
    """Return GTFS service IDs active on a date using calendar and exceptions."""
    calendar_path = feed_dir / "calendar.txt"
    calendar_dates_path = feed_dir / "calendar_dates.txt"
    service_ids: set[str] = set()

    if calendar_path.exists():
        weekday = service_date.strftime("%A").lower()
        for row in _read_csv(
            calendar_path,
            ("service_id", "start_date", "end_date", weekday),
        ):
            start = date.fromisoformat(
                f"{row['start_date'][:4]}-{row['start_date'][4:6]}-{row['start_date'][6:8]}"
            )
            end = date.fromisoformat(
                f"{row['end_date'][:4]}-{row['end_date'][4:6]}-{row['end_date'][6:8]}"
            )
            if start <= service_date <= end and row[weekday] == "1":
                service_ids.add(row["service_id"])

    if calendar_dates_path.exists():
        for row in _read_csv(calendar_dates_path, ("service_id", "date", "exception_type")):
            row_date = date.fromisoformat(
                f"{row['date'][:4]}-{row['date'][4:6]}-{row['date'][6:8]}"
            )
            if row_date == service_date:
                if row["exception_type"] == "1":
                    service_ids.add(row["service_id"])
                elif row["exception_type"] == "2":
                    service_ids.discard(row["service_id"])
                else:
                    raise FeedError(
                        f"calendar_dates.txt has unsupported exception_type "
                        f"{row['exception_type']!r}"
                    )

    if not calendar_path.exists() and not calendar_dates_path.exists():
        raise FeedError("Feed must include calendar.txt, calendar_dates.txt, or both")
    if not service_ids:
        raise FeedError(f"No active GTFS services found for {service_date.isoformat()}")
    return service_ids


def load_stop_times(feed_dir: Path, service_date: date) -> list[StopTime]:
    """Load ordered stop times for trips running on the requested service date."""
    routes = {
        row["route_id"]: row
        for row in _read_csv(feed_dir / "routes.txt", ("route_id",))
    }
    stops = {
        row["stop_id"]: row
        for row in _read_csv(feed_dir / "stops.txt", ("stop_id", "stop_name"))
    }
    active_services = active_service_ids(feed_dir, service_date)
    trip_routes: dict[str, str] = {}
    for row in _read_csv(feed_dir / "trips.txt", ("route_id", "service_id", "trip_id")):
        if row["service_id"] in active_services:
            if row["route_id"] not in routes:
                raise FeedError(f"Trip {row['trip_id']!r} refers to unknown route {row['route_id']!r}")
            trip_routes[row["trip_id"]] = row["route_id"]

    result: list[StopTime] = []
    for row in _read_csv(
        feed_dir / "stop_times.txt",
        ("trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"),
    ):
        route_id = trip_routes.get(row["trip_id"])
        if route_id is None:
            continue
        stop = stops.get(row["stop_id"])
        if stop is None:
            raise FeedError(f"Trip {row['trip_id']!r} refers to unknown stop {row['stop_id']!r}")
        try:
            sequence = int(row["stop_sequence"])
        except ValueError as exc:
            raise FeedError(f"Invalid stop_sequence for trip {row['trip_id']!r}") from exc
        result.append(
            StopTime(
                trip_id=row["trip_id"],
                route_id=route_id,
                stop_id=row["stop_id"],
                stop_name=stop["stop_name"],
                arrival_seconds=(
                    parse_gtfs_time(row["arrival_time"], field="arrival_time")
                    if row["arrival_time"].strip()
                    else None
                ),
                departure_seconds=(
                    parse_gtfs_time(row["departure_time"], field="departure_time")
                    if row["departure_time"].strip()
                    else None
                ),
                stop_sequence=sequence,
            )
        )

    if not result:
        raise FeedError(f"No stop times found for active trips on {service_date.isoformat()}")
    return result
