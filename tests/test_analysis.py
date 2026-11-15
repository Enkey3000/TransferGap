import csv
from datetime import date
from pathlib import Path

import pytest

from transfergap.analysis import find_connections, summarize, write_report

ROOT = Path(__file__).parents[1]
FEED = ROOT / "data" / "sample" / "gtfs"
OBSERVATIONS = ROOT / "data" / "sample" / "observations.csv"


def test_candidate_connections_are_scored_without_claiming_actual_missed_riders():
    connections = find_connections(
        FEED,
        date(2026, 10, 5),
        observations_path=OBSERVATIONS,
    )
    by_pair = {(row.inbound_trip_id, row.outbound_trip_id): row for row in connections}
    assert by_pair[("R1_IN_0800", "R2_OUT_0817")].status == "buffer_met"
    assert by_pair[("R1_IN_0800", "R3_OUT_0825")].status == "buffer_met"
    assert by_pair[("R1_IN_0830", "R2_OUT_0847")].status == "at_risk"
    assert by_pair[("R1_IN_0830", "R2_OUT_0847")].observed_slack_minutes == 3
    assert summarize(connections) == {
        "candidate_connections": 8,
        "observed_connections": 3,
        "at_risk_observations": 1,
    }


def test_report_writes_detail_and_stop_summary(tmp_path):
    connections = find_connections(FEED, date(2026, 10, 5), observations_path=OBSERVATIONS)
    detail, summary = write_report(connections, tmp_path)
    assert detail.is_file()
    assert summary.is_file()
    with detail.open(newline="", encoding="utf-8") as file:
        details = list(csv.DictReader(file))
        assert len(details) == 8
        assert next(row for row in details if row["status"] == "not_observed")[
            "observed_slack_minutes"
        ] == ""
    with summary.open(newline="", encoding="utf-8") as file:
        row = next(csv.DictReader(file))
    assert row["stop_name"] == "Central Exchange"
    assert row["at_risk_observations"] == "1"


def test_same_route_connections_are_excluded():
    connections = find_connections(FEED, date(2026, 10, 5), observations_path=OBSERVATIONS)
    assert all(row.inbound_route_id != row.outbound_route_id for row in connections)


def test_missing_observation_file_fails(tmp_path):
    with pytest.raises(FileNotFoundError, match="Observation file not found"):
        find_connections(
            FEED,
            date(2026, 10, 5),
            observations_path=tmp_path / "missing.csv",
        )
