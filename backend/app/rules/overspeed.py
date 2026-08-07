"""FR-14 — Overspeed.

Fires when speed exceeds the *route's* posted limit by more than the configured
tolerance. Without an assigned route there is no limit to compare against, so the
rule is skipped rather than falling back to a global constant that would be wrong
for half the fleet (UC-2 extension 2a).
"""

from __future__ import annotations

from ..enums import Severity
from .base import AlertCandidate, EvalContext

CODE = "OVERSPEED"

# How far over the tolerance counts as critical rather than a warning.
CRITICAL_MARGIN_KPH = 20.0


def evaluate(ctx: EvalContext) -> list[AlertCandidate]:
    route = ctx.route
    if route is None:
        return []

    limit = route.speed_limit_kph
    allowed = limit + ctx.thresholds.overspeed_tolerance_kph
    speed = ctx.reading.speed_kph
    if speed <= allowed:
        return []

    over_by = speed - limit
    severity = (
        Severity.CRITICAL if speed > allowed + CRITICAL_MARGIN_KPH else Severity.WARNING
    )
    return [
        AlertCandidate(
            rule_code=CODE,
            severity=severity,
            message=(
                f"{ctx.vehicle.code} travelling at {speed:.0f} kph on route "
                f"{route.code} (limit {limit:.0f} kph, {over_by:.0f} kph over)"
            ),
            measured_value=speed,
            threshold_value=allowed,
        )
    ]
