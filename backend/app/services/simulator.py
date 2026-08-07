"""Deterministic fleet telemetry simulator (FR-33 … FR-35).

Buses run their route polyline from end to end, dwelling at timetabled stops, then
start again from the beginning as the next service; trucks run their polyline once
and hold at the destination. Sensor values drift with seeded
pseudo-random noise, so a given seed always reproduces the same run (FR-34) — that
is what lets the AI-generated tests assert on simulator output at all.

Fault scenarios are armed per vehicle and ramp over time rather than jumping, so a
demonstration shows the alert crossing its threshold live instead of appearing
pre-broken.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass
from datetime import datetime, timedelta

from ..enums import VehicleType
from .geo import bearing_deg, point_at_distance, polyline_length_m

Point = tuple[float, float]

SCENARIOS = ("none", "overheat", "fuel_drain", "deviation", "dropout", "cargo_spike")

# Nominal sensor behaviour
NOMINAL_ENGINE_C = 88.0
NOMINAL_BUS_KPH = 34.0
NOMINAL_TRUCK_KPH = 58.0
FUEL_BURN_PCT_PER_KM = 0.18
DWELL_SECONDS = 20.0
SPEED_SMOOTHING = 0.45  # fraction of the gap to the target speed closed per tick

# Fault ramps are tuned so each scenario crosses its threshold roughly 60–120 s
# into a run at the default 5 s tick — fast enough to demonstrate live, slow enough
# that the examiner sees the value climb rather than teleport.
OVERHEAT_RAMP_C_PER_S = 0.30
FUEL_DRAIN_PCT_PER_TICK = 0.35
CARGO_DRIFT_C_PER_TICK = 0.22
DEVIATION_M_PER_TICK = 12.0
DROPOUT_AFTER_S = 30.0
FUEL_DRAIN_START_PCT = 26.0  # armed vehicles start near the low-fuel threshold


@dataclass(slots=True)
class SimVehicle:
    code: str
    vehicle_type: VehicleType
    polyline: list[Point]
    cruise_kph: float
    fuel_pct: float = 95.0
    engine_temp_c: float = NOMINAL_ENGINE_C
    cargo_temp_c: float | None = None
    odometer_km: float = 10_000.0
    scenario: str = "none"
    # internal state
    position_m: float = 0.0
    dwell_remaining_s: float = 0.0
    stop_offsets_m: tuple[float, ...] = ()
    elapsed_s: float = 0.0
    lateral_offset_m: float = 0.0
    # Reported speed is smoothed towards the target rather than snapped to it, so
    # pulling into a stop looks like braking and not like hitting a wall. Without
    # this the dwell logic produced a 34→0 kph step every stop and every bus tripped
    # HARSH_BRAKING — a simulator artefact masquerading as a fleet-wide problem.
    speed_kph: float = 0.0
    # Set when a bus reaches the terminus and begins the route again, i.e. starts a
    # new timetabled trip. Drained by `pop_trip_restarts()`.
    trip_restarted: bool = False

    @property
    def route_length_m(self) -> float:
        return polyline_length_m(self.polyline)


def _offset_point(point: Point, bearing: float, distance_m: float) -> Point:
    """Move a point `distance_m` perpendicular to `bearing` — used by the deviation scenario."""
    if distance_m == 0:
        return point
    perp = math.radians((bearing + 90.0) % 360.0)
    d_lat = (distance_m * math.cos(perp)) / 111_132.0
    d_lon = (distance_m * math.sin(perp)) / (111_320.0 * math.cos(math.radians(point[0])) or 1.0)
    return (point[0] + d_lat, point[1] + d_lon)


class FleetSimulator:
    """Advances a set of simulated vehicles in fixed ticks."""

    def __init__(
        self,
        vehicles: list[SimVehicle],
        *,
        seed: int = 42,
        tick_seconds: float = 5.0,
    ) -> None:
        self.vehicles = vehicles
        self.tick_seconds = tick_seconds
        self.seed = seed
        self.rng = random.Random(seed)
        self.tick_index = 0

    # ---------------------------------------------------------------- scenarios

    def arm(self, vehicle_code: str, scenario: str) -> None:
        if scenario not in SCENARIOS:
            raise ValueError(f"unknown scenario '{scenario}'; expected one of {SCENARIOS}")
        for vehicle in self.vehicles:
            if vehicle.code == vehicle_code:
                vehicle.scenario = scenario
                if scenario == "fuel_drain":
                    # A tank that starts at 95% would take an hour to reach the low
                    # threshold; arm it near the edge so the demo is watchable.
                    vehicle.fuel_pct = FUEL_DRAIN_START_PCT
                return
        raise KeyError(f"no simulated vehicle '{vehicle_code}'")

    # -------------------------------------------------------------------- step

    def step(self, now: datetime) -> list[dict]:
        """Advance every vehicle one tick and return the readings they emit.

        A vehicle in the `dropout` scenario emits nothing, which is exactly what
        the offline rule needs to observe.
        """
        dt = self.tick_seconds
        readings: list[dict] = []

        for vehicle in self.vehicles:
            vehicle.elapsed_s += dt
            self._advance(vehicle, dt)
            if vehicle.scenario == "dropout" and vehicle.elapsed_s > DROPOUT_AFTER_S:
                continue
            readings.append(self._emit(vehicle, now))

        self.tick_index += 1
        return readings

    def pop_trip_restarts(self) -> list[str]:
        """Codes of buses that began a new trip since the last call, then clear them.

        Draining rather than reading means a restart is reported exactly once, so a
        caller that fails to PATCH does not silently lose the event on the next tick
        — it simply never sees it again, which is the same contract as a queue.
        """
        codes = [v.code for v in self.vehicles if v.trip_restarted]
        for vehicle in self.vehicles:
            vehicle.trip_restarted = False
        return codes

    def run(self, start: datetime, ticks: int) -> list[dict]:
        """Convenience for tests and offline generation: run N ticks from `start`."""
        out: list[dict] = []
        for i in range(ticks):
            out.extend(self.step(start + timedelta(seconds=self.tick_seconds * i)))
        return out

    # ----------------------------------------------------------------- internals

    def _advance(self, vehicle: SimVehicle, dt: float) -> None:
        length = vehicle.route_length_m
        if length <= 0:
            return

        if vehicle.dwell_remaining_s > 0:
            vehicle.dwell_remaining_s = max(0.0, vehicle.dwell_remaining_s - dt)
            target_kph = 0.0
        else:
            target_kph = max(0.0, vehicle.cruise_kph + self.rng.uniform(-3.0, 3.0))

        vehicle.speed_kph += (target_kph - vehicle.speed_kph) * SPEED_SMOOTHING
        speed_mps = vehicle.speed_kph / 3.6

        previous = vehicle.position_m
        vehicle.position_m += speed_mps * dt

        # At the terminus a bus starts the route again from the beginning; a truck
        # holds at its destination.
        #
        # An earlier version had buses shuttle back along the route instead. That
        # broke the schedule rule: a timetable is defined in one direction only, so
        # a bus travelling backwards kept matching stops it had already served — and
        # since its trip origin never moved, elapsed time grew without bound until
        # the whole fleet reported itself late against a timetable it had finished.
        # Re-running the route models "next service from the terminus" and matches
        # the one-way timetable exactly. `trip_restarted` tells the CLI to move the
        # vehicle's schedule origin; the simulator itself stays free of I/O.
        wrapped = False
        if vehicle.position_m >= length:
            if vehicle.vehicle_type is VehicleType.BUS:
                vehicle.position_m = 0.0
                vehicle.trip_restarted = True
                wrapped = True
            else:
                vehicle.position_m = length
        elif vehicle.position_m < 0:
            vehicle.position_m = 0.0

        # Distance actually covered this tick. On the wrap the vehicle ran to the
        # terminus, not backwards to zero, so the odometer must count the remainder
        # of the route rather than the negative jump.
        travelled_km = (length - previous if wrapped else vehicle.position_m - previous) / 1000.0
        vehicle.odometer_km += max(0.0, travelled_km)

        # Dwell at a timetabled stop the vehicle has just passed. Skipped on the
        # wrap tick: `previous` and `position_m` sit at opposite ends of the route
        # there, and the naive span between them would match every stop at once.
        if not wrapped:
            for offset in vehicle.stop_offsets_m:
                if previous < offset <= vehicle.position_m:
                    vehicle.dwell_remaining_s = DWELL_SECONDS
                    break

        self._update_sensors(vehicle, dt, travelled_km, speed_mps)

    def _update_sensors(
        self, vehicle: SimVehicle, dt: float, travelled_km: float, speed_mps: float
    ) -> None:
        load = min(1.0, speed_mps / 20.0)
        target = NOMINAL_ENGINE_C + 8.0 * load + self.rng.uniform(-1.0, 1.0)

        if vehicle.scenario == "overheat":
            # Crosses the 105 °C warning then the 115 °C critical band on camera.
            target += OVERHEAT_RAMP_C_PER_S * vehicle.elapsed_s

        vehicle.engine_temp_c += (target - vehicle.engine_temp_c) * 0.25
        vehicle.engine_temp_c = round(vehicle.engine_temp_c, 2)

        burn = travelled_km * FUEL_BURN_PCT_PER_KM
        if vehicle.scenario == "fuel_drain":
            burn += FUEL_DRAIN_PCT_PER_TICK * (dt / 5.0)  # leaking tank
        vehicle.fuel_pct = round(max(0.0, vehicle.fuel_pct - burn), 2)

        if vehicle.cargo_temp_c is not None:
            drift = self.rng.uniform(-0.15, 0.15)
            if vehicle.scenario == "cargo_spike":
                drift += CARGO_DRIFT_C_PER_TICK * (dt / 5.0)  # failing refrigeration
            vehicle.cargo_temp_c = round(vehicle.cargo_temp_c + drift, 2)

        if vehicle.scenario == "deviation":
            vehicle.lateral_offset_m = min(
                600.0, vehicle.lateral_offset_m + DEVIATION_M_PER_TICK * (dt / 5.0)
            )
        else:
            vehicle.lateral_offset_m = 0.0

    def _emit(self, vehicle: SimVehicle, now: datetime) -> dict:
        point = point_at_distance(vehicle.polyline, vehicle.position_m)
        ahead = point_at_distance(
            vehicle.polyline, min(vehicle.route_length_m, vehicle.position_m + 25.0)
        )
        heading = bearing_deg(point, ahead) if point != ahead else 0.0
        if vehicle.lateral_offset_m:
            point = _offset_point(point, heading, vehicle.lateral_offset_m)

        return {
            "vehicle_code": vehicle.code,
            "recorded_at": now.isoformat(),
            "latitude": round(point[0], 6),
            "longitude": round(point[1], 6),
            "speed_kph": round(vehicle.speed_kph, 1),
            "heading_deg": round(heading, 1),
            "engine_temp_c": vehicle.engine_temp_c,
            "fuel_pct": vehicle.fuel_pct,
            "cargo_temp_c": vehicle.cargo_temp_c,
            "odometer_km": round(vehicle.odometer_km, 2),
        }


def build_from_routes(route_rows, vehicle_rows, *, seed: int = 42) -> FleetSimulator:
    """Construct a simulator from ORM Route/Vehicle rows.

    Vehicles with no assigned route, or whose route has no polyline, are skipped:
    there is nothing to drive them along.
    """
    from .geo import distance_along_polyline_m

    routes = {route.id: route for route in route_rows}
    sims: list[SimVehicle] = []

    # Spread the vehicles sharing a route evenly along it, so the demo opens with a
    # fleet in service rather than twelve markers stacked on the first waypoint.
    # Index-based, not random, so determinism (FR-34) is preserved.
    per_route: dict[int, list] = {}
    for vehicle in vehicle_rows:
        per_route.setdefault(vehicle.route_id, []).append(vehicle.code)
    position_index = {
        code: (idx, len(codes))
        for codes in per_route.values()
        for idx, code in enumerate(sorted(codes))
    }

    for vehicle in vehicle_rows:
        route = routes.get(vehicle.route_id)
        if route is None or len(route.waypoints) < 2:
            continue
        polyline = [(w.latitude, w.longitude) for w in route.waypoints]
        is_bus = vehicle.vehicle_type is VehicleType.BUS
        offsets = tuple(
            d
            for d in (
                distance_along_polyline_m(polyline, (s.latitude, s.longitude))
                for s in route.stops
            )
            if d is not None
        )
        cargo = None
        if vehicle.cargo_temp_min_c is not None and vehicle.cargo_temp_max_c is not None:
            cargo = (vehicle.cargo_temp_min_c + vehicle.cargo_temp_max_c) / 2.0

        index, count = position_index[vehicle.code]
        start_m = polyline_length_m(polyline) * (index / max(count, 1)) * 0.8

        sims.append(
            SimVehicle(
                code=vehicle.code,
                vehicle_type=vehicle.vehicle_type,
                polyline=polyline,
                cruise_kph=NOMINAL_BUS_KPH if is_bus else NOMINAL_TRUCK_KPH,
                cargo_temp_c=cargo,
                stop_offsets_m=offsets if is_bus else (),
                position_m=start_m,
            )
        )

    return FleetSimulator(sims, seed=seed)
