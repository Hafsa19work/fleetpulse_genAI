"""FR-17 — Route deviation (geofence).

Measures the perpendicular distance from the vehicle to its route polyline and
compares it against the route's own corridor half-width. A polyline needs at
least two points to define a corridor; with fewer, the rule is skipped.
"""

from __future__ import annotations

from ..enums import Severity
from ..services.geo import distance_to_polyline_m
from .base import AlertCandidate, EvalContext

CODE = "ROUTE_DEVIATION"

# Beyond this multiple of the corridor the vehicle is not merely drifting.
CRITICAL_FACTOR = 3.0


def evaluate(ctx: EvalContext) -> list[AlertCandidate]:
    route = ctx.route
    if route is None or len(route.polyline) < 2:
        return []

    distance = distance_to_polyline_m(list(route.polyline), ctx.reading.position)
    if distance is None:
        return []

    corridor = route.corridor_half_width_m
    if distance <= corridor:
        return []

    severity = (
        Severity.CRITICAL if distance > corridor * CRITICAL_FACTOR else Severity.WARNING
    )
    return [
        AlertCandidate(
            rule_code=CODE,
            severity=severity,
            message=(
                f"{ctx.vehicle.code} is {distance:.0f} m from route {route.code} "
                f"(corridor {corridor:.0f} m)"
            ),
            measured_value=distance,
            threshold_value=corridor,
        )
    ]
