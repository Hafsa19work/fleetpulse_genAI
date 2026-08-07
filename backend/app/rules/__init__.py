"""The rule registry.

Adding a rule means writing one pure module and appending one `Rule(...)` entry
here. The engine iterates this list and never names an individual rule, so no
engine change is required — including for vehicle-type-gated rules, where the
gating is expressed by `applies_to` rather than by a branch in the engine.
"""

from __future__ import annotations

from ..enums import VehicleType
from . import (
    cargo_temp,
    deviation,
    engine_temp,
    fuel,
    harsh_braking,
    offline,
    overspeed,
    schedule,
)
from .base import (
    AlertCandidate,
    EvalContext,
    Reading,
    Rule,
    RouteCtx,
    StopCtx,
    VehicleCtx,
)

BOTH = frozenset(VehicleType)
BUS_ONLY = frozenset({VehicleType.BUS})
TRUCK_ONLY = frozenset({VehicleType.TRUCK})

RULES: tuple[Rule, ...] = (
    Rule(overspeed.CODE, overspeed.evaluate, BOTH, "Speed over the route limit + tolerance"),
    Rule(engine_temp.CODE, engine_temp.evaluate, BOTH, "Engine temperature above threshold"),
    Rule(fuel.CODE, fuel.evaluate, BOTH, "Fuel level below threshold"),
    Rule(deviation.CODE, deviation.evaluate, BOTH, "Outside the route corridor"),
    Rule(offline.CODE, offline.evaluate, BOTH, "No telemetry within the heartbeat timeout"),
    Rule(harsh_braking.CODE, harsh_braking.evaluate, BOTH, "Excessive deceleration"),
    Rule(schedule.CODE, schedule.evaluate, BUS_ONLY, "Projected late at the next stop"),
    Rule(cargo_temp.CODE, cargo_temp.evaluate, TRUCK_ONLY, "Cargo outside its temperature band"),
)

RULES_BY_CODE: dict[str, Rule] = {rule.code: rule for rule in RULES}

__all__ = [
    "BOTH",
    "BUS_ONLY",
    "RULES",
    "RULES_BY_CODE",
    "TRUCK_ONLY",
    "AlertCandidate",
    "EvalContext",
    "Reading",
    "Rule",
    "RouteCtx",
    "StopCtx",
    "VehicleCtx",
]
