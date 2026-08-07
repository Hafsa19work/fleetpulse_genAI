"""FR-21 — Cargo temperature excursion. Trucks only.

The permitted band lives on the vehicle, not in the global threshold set: a frozen
load and a chilled load travel in the same fleet under different limits. A vehicle
with no band configured is not refrigerated, so the rule does not apply.

Severity scales with how far outside the band the load has drifted, because one
degree over for a minute is recoverable and five degrees over is a written-off load.
"""

from __future__ import annotations

from ..enums import Severity, VehicleType
from .base import AlertCandidate, EvalContext

CODE = "CARGO_TEMP_EXCURSION"

CRITICAL_EXCURSION_C = 3.0


def evaluate(ctx: EvalContext) -> list[AlertCandidate]:
    vehicle = ctx.vehicle
    if vehicle.vehicle_type is not VehicleType.TRUCK:
        return []

    temp = ctx.reading.cargo_temp_c
    lo, hi = vehicle.cargo_temp_min_c, vehicle.cargo_temp_max_c
    if temp is None or (lo is None and hi is None):
        return []

    if hi is not None and temp > hi:
        excursion, threshold, direction = temp - hi, hi, "above"
    elif lo is not None and temp < lo:
        excursion, threshold, direction = lo - temp, lo, "below"
    else:
        return []

    severity = (
        Severity.CRITICAL if excursion >= CRITICAL_EXCURSION_C else Severity.WARNING
    )
    return [
        AlertCandidate(
            rule_code=CODE,
            severity=severity,
            message=(
                f"{vehicle.code} cargo at {temp:.1f} °C — {excursion:.1f} °C "
                f"{direction} the permitted limit of {threshold:.1f} °C"
            ),
            measured_value=temp,
            threshold_value=threshold,
        )
    ]
