"""Runtime threshold tuning (FR-22, UC-7) and rule introspection."""

from __future__ import annotations

from dataclasses import asdict

from fastapi import APIRouter, HTTPException, status

from ..config import get_thresholds, reset_thresholds, set_thresholds
from ..rules import RULES
from ..schemas import RuleInfo, ThresholdsRead, ThresholdsUpdate

router = APIRouter(prefix="/api/config", tags=["config"])


@router.get("/thresholds", response_model=ThresholdsRead)
def read_thresholds() -> ThresholdsRead:
    return ThresholdsRead(**asdict(get_thresholds()))


@router.put("/thresholds", response_model=ThresholdsRead)
def update_thresholds(payload: ThresholdsUpdate) -> ThresholdsRead:
    changes = payload.model_dump(exclude_unset=True)
    merged = get_thresholds().merged(**changes)

    # Cross-field invariants Pydantic cannot express field-by-field: a critical
    # band that sits on the wrong side of its warning band would silently make one
    # of the two unreachable.
    if merged.engine_critical_c <= merged.engine_warn_c:
        raise HTTPException(
            422,
            detail="engine_critical_c must be greater than engine_warn_c",
        )
    if merged.fuel_critical_pct >= merged.fuel_low_pct:
        raise HTTPException(
            422,
            detail="fuel_critical_pct must be less than fuel_low_pct",
        )

    return ThresholdsRead(**asdict(set_thresholds(merged)))


@router.post("/thresholds/reset", response_model=ThresholdsRead)
def reset() -> ThresholdsRead:
    return ThresholdsRead(**asdict(reset_thresholds()))


@router.get("/rules", response_model=list[RuleInfo])
def list_rules() -> list[RuleInfo]:
    return [
        RuleInfo(
            code=rule.code,
            description=rule.description,
            applies_to=sorted(rule.applies_to, key=lambda t: t.value),
        )
        for rule in RULES
    ]
