"""FR-19 — Harsh braking.

Compares consecutive readings. Requires a previous reading and a strictly positive
time gap; a zero or negative gap (clock skew, out-of-order delivery) would make the
deceleration meaningless, so the rule declines to judge rather than dividing by
zero — defect D-02 in the AI review pass.

Only gaps within `harsh_braking_window_s` are considered: a 60 kph drop measured
across a ten-minute gap says nothing about how hard the driver braked.
"""

from __future__ import annotations

from ..enums import Severity
from .base import AlertCandidate, EvalContext

CODE = "HARSH_BRAKING"

CRITICAL_FACTOR = 1.6


def evaluate(ctx: EvalContext) -> list[AlertCandidate]:
    previous = ctx.previous
    if previous is None:
        return []

    gap_s = (ctx.reading.recorded_at - previous.recorded_at).total_seconds()
    if gap_s <= 0 or gap_s > ctx.thresholds.harsh_braking_window_s:
        return []

    drop_kph = previous.speed_kph - ctx.reading.speed_kph
    threshold = ctx.thresholds.harsh_braking_delta_kph
    if drop_kph <= threshold:
        return []

    decel_kph_per_s = drop_kph / gap_s
    severity = (
        Severity.WARNING if drop_kph < threshold * CRITICAL_FACTOR else Severity.CRITICAL
    )
    return [
        AlertCandidate(
            rule_code=CODE,
            severity=severity,
            message=(
                f"{ctx.vehicle.code} lost {drop_kph:.0f} kph in {gap_s:.0f} s "
                f"({decel_kph_per_s:.1f} kph/s deceleration)"
            ),
            measured_value=drop_kph,
            threshold_value=threshold,
        )
    ]
