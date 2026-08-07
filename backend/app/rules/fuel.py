"""FR-16 — Low fuel.

Mirror image of the engine rule: two bands, but the comparison is *below* rather
than above. Kept as its own module rather than a shared parametrised helper,
because the message wording and the severity semantics differ and a shared helper
would have to be configured with more parameters than it saves.
"""

from __future__ import annotations

from ..enums import Severity
from .base import AlertCandidate, EvalContext

CODE = "LOW_FUEL"


def evaluate(ctx: EvalContext) -> list[AlertCandidate]:
    fuel = ctx.reading.fuel_pct
    if fuel is None:
        return []

    th = ctx.thresholds
    if fuel < th.fuel_critical_pct:
        severity, threshold = Severity.CRITICAL, th.fuel_critical_pct
    elif fuel < th.fuel_low_pct:
        severity, threshold = Severity.WARNING, th.fuel_low_pct
    else:
        return []

    return [
        AlertCandidate(
            rule_code=CODE,
            severity=severity,
            message=(
                f"{ctx.vehicle.code} fuel level {fuel:.0f}% is below {threshold:.0f}%"
            ),
            measured_value=fuel,
            threshold_value=threshold,
        )
    ]
