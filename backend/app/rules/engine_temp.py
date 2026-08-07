"""FR-15 — Engine overheating.

Two-band rule: above the warning threshold is a `warning`, above the critical
threshold is a `critical`. A reading with no engine temperature (a telematics unit
without that sensor) yields no candidate — a missing sensor is not a fault.
"""

from __future__ import annotations

from ..enums import Severity
from .base import AlertCandidate, EvalContext

CODE = "ENGINE_OVERHEAT"


def evaluate(ctx: EvalContext) -> list[AlertCandidate]:
    temp = ctx.reading.engine_temp_c
    if temp is None:
        return []

    th = ctx.thresholds
    if temp > th.engine_critical_c:
        severity, threshold = Severity.CRITICAL, th.engine_critical_c
    elif temp > th.engine_warn_c:
        severity, threshold = Severity.WARNING, th.engine_warn_c
    else:
        return []

    return [
        AlertCandidate(
            rule_code=CODE,
            severity=severity,
            message=(
                f"{ctx.vehicle.code} engine temperature {temp:.1f} °C "
                f"exceeds {threshold:.0f} °C"
            ),
            measured_value=temp,
            threshold_value=threshold,
        )
    ]
