"""Telemetry ingestion endpoints (FR-09 … FR-11, UC-1)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from ..database import get_session
from ..schemas import (
    AlertRead,
    BatchIngestResult,
    IngestResult,
    TelemetryBatch,
    TelemetryCreate,
)
from ..services import ingestion

router = APIRouter(prefix="/api/telemetry", tags=["telemetry"])


def _alert_payload(alert, vehicle_code: str) -> AlertRead:  # noqa: ANN001
    from ..services.alerts import duration_seconds

    data = AlertRead.model_validate(alert)
    return data.model_copy(
        update={"vehicle_code": vehicle_code, "duration_seconds": duration_seconds(alert)}
    )


@router.post("", response_model=IngestResult, status_code=status.HTTP_202_ACCEPTED)
def ingest_reading(
    payload: TelemetryCreate, session: Session = Depends(get_session)
) -> IngestResult:
    try:
        outcome = ingestion.ingest(session, payload)
    except ingestion.VehicleNotFound as exc:
        raise HTTPException(status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return IngestResult(
        vehicle_code=outcome.vehicle.code,
        reading_id=outcome.reading_row.id if outcome.reading_row else None,
        duplicate=outcome.duplicate,
        evaluated=outcome.evaluated,
        alerts_created=[_alert_payload(a, outcome.vehicle.code) for a in outcome.created],
        alerts_updated=[_alert_payload(a, outcome.vehicle.code) for a in outcome.updated],
        failed_rules=outcome.failed_rules,
    )


@router.post("/batch", response_model=BatchIngestResult, status_code=status.HTTP_202_ACCEPTED)
def ingest_batch(
    payload: TelemetryBatch, session: Session = Depends(get_session)
) -> BatchIngestResult:
    """Best-effort batch (FR-10).

    One bad reading does not discard the batch: it is counted, its reason is
    reported, and the rest are still ingested. A batch from a field device that
    buffered overnight will usually contain at least one malformed row, and
    rejecting the whole upload would lose a night of good data.
    """
    accepted = duplicates = rejected = created = 0
    errors: list[str] = []

    for index, reading in enumerate(payload.readings):
        try:
            outcome = ingestion.ingest(session, reading)
        except ingestion.VehicleNotFound as exc:
            rejected += 1
            if len(errors) < 20:
                errors.append(f"[{index}] {exc}")
            continue
        except Exception as exc:  # noqa: BLE001
            session.rollback()
            rejected += 1
            if len(errors) < 20:
                errors.append(f"[{index}] {type(exc).__name__}: {exc}")
            continue

        if outcome.duplicate:
            duplicates += 1
        else:
            accepted += 1
        created += len(outcome.created)

    return BatchIngestResult(
        accepted=accepted,
        duplicates=duplicates,
        rejected=rejected,
        alerts_created=created,
        errors=errors,
    )
