"""FR-18 — Vehicle offline (heartbeat timeout).

"No data arrived" cannot be observed from an arriving reading, so this rule is
driven by the periodic sweeper (design decision D-7) with `ctx.reading` set to the
vehicle's *last known* reading and `ctx.now` set to the sweep time.

It is still evaluated on the ingestion path, where the age is near zero and the
rule correctly stays silent. That symmetry means the same rule function serves
both callers and only needs testing once.
"""

from __future__ import annotations

from ..enums import Severity
from .base import AlertCandidate, EvalContext

CODE = "VEHICLE_OFFLINE"


def evaluate(ctx: EvalContext) -> list[AlertCandidate]:
    timeout = ctx.thresholds.heartbeat_timeout_s
    age_s = (ctx.now - ctx.reading.recorded_at).total_seconds()
    if age_s <= timeout:
        return []

    minutes = age_s / 60.0
    return [
        AlertCandidate(
            rule_code=CODE,
            severity=Severity.CRITICAL,
            message=(
                f"{ctx.vehicle.code} has not reported for {minutes:.1f} min "
                f"(timeout {timeout / 60:.1f} min)"
            ),
            measured_value=age_s,
            threshold_value=timeout,
        )
    ]
