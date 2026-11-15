# TransferGap

**Find where scheduled transit connections may be fragile—then show the evidence, not
just a red dot on a map.**

TransferGap is a reproducible data-analysis project that reads a GTFS static feed,
finds candidate same-stop connections between different routes, and optionally scores
those candidates using sampled inbound vehicle arrivals. It produces plain CSV reports
that planners can inspect and reproduce.

> **Important:** TransferGap does not know whether a passenger tried to make a
> connection. `at_risk` means the sampled inbound arrival left less than the configured
> buffer before the scheduled outbound departure. It does **not** prove a passenger
> missed a transfer. The included feed and observations are synthetic.

## Why this project

Schedule and vehicle-location data can help agencies identify connections worth
investigating. The goal is to turn that data into a transparent screening tool for
service planning—not to overstate what operational data alone can prove.

## What is included

- A dependency-light Python package and command-line interface.
- GTFS service-date filtering, including `calendar_dates.txt` exceptions and after-
  midnight GTFS times.
- Candidate connection analysis with configurable transfer-buffer and maximum-wait
  windows.
- Optional observed inbound arrival scoring.
- Detailed connection and stop-level CSV reports.
- A tiny synthetic GTFS fixture and tests that run locally and in GitHub Actions.

## Quick start

Requires Python 3.10 or later.

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -e ".[dev]"
transfergap analyze `
  --gtfs data/sample/gtfs `
  --date 2026-10-05 `
  --observations data/sample/observations.csv `
  --output-dir reports
pytest
ruff check .
```

Or run without installing the package entry point:

```powershell
$env:PYTHONPATH = "src"
python -m transfergap.cli analyze --gtfs data/sample/gtfs --date 2026-10-05 --observations data/sample/observations.csv --output-dir reports
```

The sample produces:

- `reports/candidate_connections.csv` — candidate route-to-route connections, schedule
  slack, optional observed arrival/slack, and a conservative status.
- `reports/stop_summary.csv` — candidate and observed counts, with an at-risk
  percentage calculated only over observed candidates.

Expected sample summary:

```json
{
  "candidate_connections": 8,
  "observed_connections": 3,
  "at_risk_observations": 1
}
```

## Input data

The GTFS directory must contain `routes.txt`, `stops.txt`, `trips.txt`,
`stop_times.txt`, and at least one of `calendar.txt` or `calendar_dates.txt`. The
optional observation CSV requires:

```csv
trip_id,stop_id,arrival_time
R1_IN_0800,HUB,08:05:00
```

Observation times use the GTFS service-day `HH:MM:SS` format; hours greater than 23 are
supported. For production use, document timezone, service date, sensor provenance, and
data coverage. See [the methodology](docs/methodology.md).

## Project structure

```text
TransferGap/
├── .github/workflows/ci.yml
├── data/sample/
│   ├── gtfs/                 # Small synthetic GTFS static feed
│   └── observations.csv      # Synthetic inbound arrival observations
├── docs/methodology.md
├── reports/                  # Generated CSVs (not committed)
├── src/transfergap/          # GTFS parsing, analysis, CLI
├── tests/
├── pyproject.toml
└── README.md
```

## Assumptions and next steps

The first version deliberately uses same-stop, cross-route pairs and a minimum walking/
boarding buffer as configurable screening rules. It does not model station pathways,
passenger demand, transfer intent, vehicle holding, or causal impact. A next iteration
could add GTFS pathway and transfer rules, multi-day reliability summaries, real-time
feed ingestion, and a map/dashboard after validating the analysis against agency
stakeholders and approved operational data.

## Responsible use

Use public, synthetic, or appropriately authorized data. Aggregate reports before
sharing. Do not use this prototype to make rider-level determinations, rank individual
staff, or claim that a connection was missed without passenger-level evidence.

## License

MIT. See [LICENSE](LICENSE).
