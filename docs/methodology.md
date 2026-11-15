# Methodology and interpretation

## What this prototype measures

TransferGap identifies **candidate scheduled connections** where a trip on one route is
scheduled to arrive at a stop before a different route departs from that same stop. It
then optionally compares sampled inbound arrival observations with the scheduled
outbound departure and a configurable minimum transfer buffer.

The sample data is synthetic and for demonstration only. It is not a real agency feed.

## What it does not measure

The prototype has no passenger-level tap, itinerary, or transfer-attempt data. It cannot
determine whether a passenger intended to make a connection, was on the inbound vehicle,
or actually missed an outbound vehicle. An `at_risk` result means only that the sampled
inbound arrival leaves less than the configured buffer before the scheduled departure.
It is a screening signal, not a rider outcome, service-causality finding, or performance
guarantee.

## Analysis steps

1. Select the trips active on a requested GTFS service date using `calendar.txt` and
   `calendar_dates.txt`.
2. Read trips, routes, stops, and ordered stop times; support GTFS times beyond 24:00.
3. Generate same-stop, cross-route candidates whose scheduled slack falls within the
   configured minimum buffer and maximum wait window.
4. If observations are provided, match observed inbound arrivals by `(trip_id, stop_id)`.
5. Label each candidate `at_risk`, `buffer_met`, or `not_observed` and write detailed
   and stop-level CSV reports.

## Limitations and next validation steps

- Candidate generation uses the same physical stop ID; it does not model walking
  distances, station pathways, fare constraints, accessibility, or transfer rules.
- The prototype does not pair trips into passenger itineraries or model whether an
  outbound vehicle waits.
- Observation timestamps are interpreted as GTFS service-day `HH:MM:SS`, not arbitrary
  wall-clock timestamps. Production data needs explicit service date, timezone, and
  daylight-saving handling.
- Each supplied observation is treated as one measurement; production feeds need
  provenance, freshness checks, deduplication policy, and coverage reporting.
- Validate on multiple service dates and routes; review candidate pairs with transit
  planners; compare observed samples with authoritative agency data.
- Report sample coverage and confidence before using findings for schedule decisions.
