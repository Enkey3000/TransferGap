"""Candidate transfer generation and observed-arrival risk scoring."""

from __future__ import annotations

import csv
from collections import defaultdict
from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path

from transfergap.gtfs import StopTime, format_gtfs_time, load_stop_times, parse_gtfs_time


@dataclass(frozen=True)
class Connection:
    service_date: str
    stop_id: str
    stop_name: str
    inbound_trip_id: str
    inbound_route_id: str
    inbound_arrival: str
    outbound_trip_id: str
    outbound_route_id: str
    outbound_departure: str
    scheduled_slack_minutes: float
    observed_inbound_arrival: str
    observed_slack_minutes: float | None
    status: str


def _read_observations(path: Path | None) -> dict[tuple[str, str], int]:
    if path is None:
        return {}
    if not path.is_file():
        raise FileNotFoundError(f"Observation file not found: {path}")
    observations: dict[tuple[str, str], int] = {}
    with path.open(newline="", encoding="utf-8-sig") as file:
        reader = csv.DictReader(file)
        required = {"trip_id", "stop_id", "arrival_time"}
        missing = required - set(reader.fieldnames or ())
        if missing:
            raise ValueError(f"Observation CSV is missing columns: {', '.join(sorted(missing))}")
        for row in reader:
            key = (row["trip_id"].strip(), row["stop_id"].strip())
            if not all(key):
                raise ValueError("Observation CSV trip_id and stop_id must be non-empty")
            if key in observations:
                raise ValueError(f"Duplicate observation for trip {key[0]!r}, stop {key[1]!r}")
            observations[key] = parse_gtfs_time(row["arrival_time"], field="observed arrival_time")
    return observations


def find_connections(
    feed_dir: Path,
    service_date: date,
    *,
    max_wait_minutes: int = 30,
    min_transfer_minutes: int = 5,
    observations_path: Path | None = None,
) -> list[Connection]:
    """Find cross-route same-stop candidate connections and score observed inbound arrivals."""
    if max_wait_minutes <= 0:
        raise ValueError("max_wait_minutes must be positive")
    if min_transfer_minutes < 0:
        raise ValueError("min_transfer_minutes must be non-negative")

    stop_times = load_stop_times(feed_dir, service_date)
    observations = _read_observations(observations_path)
    arrivals: dict[str, list[StopTime]] = defaultdict(list)
    departures: dict[str, list[StopTime]] = defaultdict(list)
    for item in stop_times:
        if item.arrival_seconds is not None:
            arrivals[item.stop_id].append(item)
        if item.departure_seconds is not None:
            departures[item.stop_id].append(item)

    max_wait_seconds = max_wait_minutes * 60
    min_transfer_seconds = min_transfer_minutes * 60
    rows: list[Connection] = []
    for stop_id, incoming in arrivals.items():
        for arriving_trip in incoming:
            observed_arrival = observations.get((arriving_trip.trip_id, stop_id))
            for departing_trip in departures.get(stop_id, []):
                if arriving_trip.trip_id == departing_trip.trip_id:
                    continue
                if arriving_trip.route_id == departing_trip.route_id:
                    continue
                assert arriving_trip.arrival_seconds is not None
                assert departing_trip.departure_seconds is not None
                scheduled_slack = departing_trip.departure_seconds - arriving_trip.arrival_seconds
                if not min_transfer_seconds <= scheduled_slack <= max_wait_seconds:
                    continue
                observed_slack = (
                    departing_trip.departure_seconds - observed_arrival
                    if observed_arrival is not None
                    else None
                )
                if observed_slack is None:
                    status = "not_observed"
                elif observed_slack < min_transfer_seconds:
                    status = "at_risk"
                else:
                    status = "buffer_met"
                rows.append(
                    Connection(
                        service_date=service_date.isoformat(),
                        stop_id=stop_id,
                        stop_name=arriving_trip.stop_name,
                        inbound_trip_id=arriving_trip.trip_id,
                        inbound_route_id=arriving_trip.route_id,
                        inbound_arrival=format_gtfs_time(arriving_trip.arrival_seconds),
                        outbound_trip_id=departing_trip.trip_id,
                        outbound_route_id=departing_trip.route_id,
                        outbound_departure=format_gtfs_time(departing_trip.departure_seconds),
                        scheduled_slack_minutes=round(scheduled_slack / 60, 2),
                        observed_inbound_arrival=(
                            format_gtfs_time(observed_arrival) if observed_arrival is not None else ""
                        ),
                        observed_slack_minutes=(
                            round(observed_slack / 60, 2) if observed_slack is not None else None
                        ),
                        status=status,
                    )
                )
    return sorted(
        rows,
        key=lambda item: (
            item.stop_name.casefold(),
            item.inbound_route_id,
            item.outbound_route_id,
            item.inbound_arrival,
        ),
    )


def write_report(connections: list[Connection], output_dir: Path) -> tuple[Path, Path]:
    """Write detailed candidate connections and a compact summary CSV."""
    output_dir.mkdir(parents=True, exist_ok=True)
    detail_path = output_dir / "candidate_connections.csv"
    summary_path = output_dir / "stop_summary.csv"

    fields = list(asdict(connections[0]).keys()) if connections else list(Connection.__dataclass_fields__)
    with detail_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        for row in connections:
            writer.writerow(asdict(row))

    by_stop: dict[tuple[str, str], list[Connection]] = defaultdict(list)
    for row in connections:
        by_stop[(row.stop_id, row.stop_name)].append(row)
    with summary_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.DictWriter(
            file,
            fieldnames=(
                "stop_id",
                "stop_name",
                "candidate_connections",
                "observed_connections",
                "at_risk_observations",
                "risk_rate_percent",
            ),
        )
        writer.writeheader()
        for (stop_id, stop_name), rows in sorted(by_stop.items(), key=lambda entry: entry[0][1].casefold()):
            observed = [row for row in rows if row.status != "not_observed"]
            at_risk = sum(row.status == "at_risk" for row in observed)
            writer.writerow(
                {
                    "stop_id": stop_id,
                    "stop_name": stop_name,
                    "candidate_connections": len(rows),
                    "observed_connections": len(observed),
                    "at_risk_observations": at_risk,
                    "risk_rate_percent": (
                        round(100 * at_risk / len(observed), 1) if observed else ""
                    ),
                }
            )
    return detail_path, summary_path


def summarize(connections: list[Connection]) -> dict[str, int]:
    """Return counts with explicit separation between candidates and observations."""
    return {
        "candidate_connections": len(connections),
        "observed_connections": sum(row.status != "not_observed" for row in connections),
        "at_risk_observations": sum(row.status == "at_risk" for row in connections),
    }
