"""Rule engine orchestration: gating, isolation, registry. AI-generated (P-17, P-19)."""

from __future__ import annotations

from app.enums import Severity, VehicleType
from app.rules import BUS_ONLY, RULES, RULES_BY_CODE, AlertCandidate, Rule
from app.services import monitoring
from conftest import make_ctx, make_reading, make_truck, make_vehicle


def test_registry_has_all_eight_rules():
    assert len(RULES) == 8
    assert set(RULES_BY_CODE) == {
        "OVERSPEED",
        "ENGINE_OVERHEAT",
        "LOW_FUEL",
        "ROUTE_DEVIATION",
        "VEHICLE_OFFLINE",
        "HARSH_BRAKING",
        "SCHEDULE_DELAY",
        "CARGO_TEMP_EXCURSION",
    }


def test_every_rule_has_a_description():
    assert all(rule.description for rule in RULES)


def test_bus_gating_skips_the_truck_rule():
    result = monitoring.evaluate(make_ctx(vehicle=make_vehicle()))
    assert "CARGO_TEMP_EXCURSION" in result.skipped_rules
    assert "SCHEDULE_DELAY" not in result.skipped_rules


def test_truck_gating_skips_the_bus_rule():
    result = monitoring.evaluate(make_ctx(vehicle=make_truck()))
    assert "SCHEDULE_DELAY" in result.skipped_rules
    assert "CARGO_TEMP_EXCURSION" not in result.skipped_rules


def test_healthy_reading_produces_nothing():
    result = monitoring.evaluate(make_ctx())
    assert result.candidates == []
    assert result.failed_rules == {}


def test_multiple_faults_produce_multiple_candidates():
    reading = make_reading(speed_kph=95.0, engine_temp_c=125.0, fuel_pct=4.0)
    result = monitoring.evaluate(make_ctx(reading=reading))
    codes = {candidate.rule_code for candidate in result.candidates}
    assert codes == {"OVERSPEED", "ENGINE_OVERHEAT", "LOW_FUEL"}
    assert all(c.severity is Severity.CRITICAL for c in result.candidates)


def test_a_raising_rule_does_not_suppress_the_others():
    """NFR-09 / defect D-04: rule isolation.

    A rule that throws must be recorded and the rest must still run — a bug in the
    cargo rule can never hide an overheating engine.
    """

    def exploding(_ctx):
        raise ZeroDivisionError("simulated rule bug")

    def working(_ctx):
        return [AlertCandidate("WORKS", Severity.INFO, "still evaluated")]

    rules = (
        Rule("BOOM", exploding),
        Rule("WORKS", working),
    )
    result = monitoring.evaluate(make_ctx(), rules=rules)

    assert "BOOM" in result.failed_rules
    assert "ZeroDivisionError" in result.failed_rules["BOOM"]
    assert [c.rule_code for c in result.candidates] == ["WORKS"]


def test_gating_is_data_not_a_branch_in_the_engine():
    bus_rule = Rule("BUS_THING", lambda _c: [], BUS_ONLY)
    assert bus_rule.applicable(VehicleType.BUS)
    assert not bus_rule.applicable(VehicleType.TRUCK)


def test_evaluation_does_not_mutate_the_context():
    """Rules are pure: the context they were handed must come back unchanged."""
    ctx = make_ctx(reading=make_reading(speed_kph=95.0, engine_temp_c=125.0))
    before = (ctx.reading, ctx.vehicle, ctx.route, ctx.thresholds, ctx.now)
    monitoring.evaluate(ctx)
    assert (ctx.reading, ctx.vehicle, ctx.route, ctx.thresholds, ctx.now) == before
