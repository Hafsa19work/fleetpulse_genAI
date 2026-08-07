"""FR-20 — Schedule delay. Buses only.

Projects the bus's arrival at its next timetabled stop and compares it with that
stop's scheduled offset from the start of the trip.

  elapsed        = now_of_reading - trip_started_at
  along_vehicle  = arc length of the vehicle's projection onto the route polyline
  along_stop     = same, for the stop
  remaining      = along_stop - along_vehicle
  average_speed  = along_vehicle / elapsed        <-- not the instantaneous speed
  projected_eta  = elapsed + remaining / average_speed
  delay          = projected_eta - stop.scheduled_offset_s

**Why average speed and not the speed in the reading.** Instantaneous speed is a
terrible estimator of how long the rest of a leg will take, because a bus spends a
large fraction of its time at a stop or accelerating away from one. Projecting a
2 km leg from a momentary 6 kph gives a twenty-minute ETA and a false critical
alert — defect D-09, which is exactly what happened to the whole fleet in the
containerised demo. Average speed since the trip began already has dwell time,
traffic and acceleration baked into it, which is precisely what "will it arrive on
time?" depends on.

A bus that has not moved at all has no meaningful average. Rather than skip — which
would silently ignore the worst case, a bus broken down between stops — the rule
falls back to the delay *already accrued*, `elapsed - scheduled_offset_s`. That is
a lower bound on the true delay, so the alert is conservative but never spurious.
"""

from __future__ import annotations

from ..enums import Severity, VehicleType
from ..services.geo import distance_along_polyline_m
from .base import AlertCandidate, EvalContext, StopCtx

CODE = "SCHEDULE_DELAY"

CRITICAL_FACTOR = 2.0


def _next_stop(ctx: EvalContext, along_vehicle: float) -> tuple[StopCtx, float] | None:
    """The first stop ahead of the vehicle, with its arc length along the route."""
    route = ctx.route
    assert route is not None  # guarded by the caller
    polyline = list(route.polyline)
    for stop in sorted(route.stops, key=lambda s: s.sequence):
        along_stop = distance_along_polyline_m(polyline, stop.position)
        if along_stop is None:
            continue
        if along_stop > along_vehicle:
            return stop, along_stop
    return None


def evaluate(ctx: EvalContext) -> list[AlertCandidate]:
    if ctx.vehicle.vehicle_type is not VehicleType.BUS:
        return []

    route = ctx.route
    trip_start = ctx.vehicle.trip_started_at
    if route is None or trip_start is None or not route.stops or len(route.polyline) < 2:
        return []

    elapsed_s = (ctx.reading.recorded_at - trip_start).total_seconds()
    if elapsed_s < 0:
        # Reading predates the trip start — bad data, not a delay.
        return []

    along_vehicle = distance_along_polyline_m(list(route.polyline), ctx.reading.position)
    if along_vehicle is None:
        return []

    upcoming = _next_stop(ctx, along_vehicle)
    if upcoming is None:
        # Past the final stop; the trip is over as far as this rule is concerned.
        return []
    stop, along_stop = upcoming

    remaining_m = along_stop - along_vehicle
    th = ctx.thresholds

    # Average speed achieved so far, which already accounts for dwell time at stops
    # and for acceleration — unlike the instantaneous speed in the reading.
    average_mps = along_vehicle / elapsed_s if elapsed_s > 0 else 0.0

    if average_mps >= th.schedule_min_speed_kph / 3.6:
        projected_s = elapsed_s + remaining_m / average_mps
    else:
        # Barely moved since the trip began: no meaningful average, so fall back to
        # the delay already accrued rather than inventing an arrival time.
        projected_s = elapsed_s

    delay_s = projected_s - stop.scheduled_offset_s
    if delay_s <= th.schedule_grace_s:
        return []

    severity = (
        Severity.CRITICAL
        if delay_s > th.schedule_grace_s * CRITICAL_FACTOR
        else Severity.WARNING
    )
    return [
        AlertCandidate(
            rule_code=CODE,
            severity=severity,
            message=(
                f"{ctx.vehicle.code} projected {delay_s / 60:.1f} min late for stop "
                f"'{stop.name}' on route {route.code}"
            ),
            measured_value=delay_s,
            threshold_value=th.schedule_grace_s,
        )
    ]
