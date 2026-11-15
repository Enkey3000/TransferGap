"""Command-line entry point for TransferGap."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

from transfergap.analysis import find_connections, summarize, write_report
from transfergap.gtfs import FeedError


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="transfergap",
        description="Analyze candidate transit transfers from GTFS schedules and observed arrivals.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    analyze = subparsers.add_parser("analyze", help="generate candidate connection and stop reports")
    analyze.add_argument("--gtfs", type=Path, required=True, help="directory containing GTFS .txt files")
    analyze.add_argument("--date", type=date.fromisoformat, required=True, help="service date (YYYY-MM-DD)")
    analyze.add_argument(
        "--observations",
        type=Path,
        help="optional CSV with trip_id,stop_id,arrival_time columns",
    )
    analyze.add_argument("--max-wait-minutes", type=int, default=30)
    analyze.add_argument("--min-transfer-minutes", type=int, default=5)
    analyze.add_argument("--output-dir", type=Path, default=Path("reports"))
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        connections = find_connections(
            args.gtfs,
            args.date,
            max_wait_minutes=args.max_wait_minutes,
            min_transfer_minutes=args.min_transfer_minutes,
            observations_path=args.observations,
        )
        detail_path, summary_path = write_report(connections, args.output_dir)
    except (FeedError, OSError, ValueError) as exc:
        print(f"transfergap: error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(summarize(connections), indent=2))
    print(f"Detailed report: {detail_path}")
    print(f"Stop summary: {summary_path}")
    print(
        "Interpretation: an at-risk observation means the sampled inbound arrival left less "
        "than the configured transfer buffer before a scheduled outbound departure. "
        "It does not establish that a passenger attempted or missed the connection."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
