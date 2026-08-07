"""Database engine, session factory and the UTC helper.

The `ensure_utc` helper exists because SQLite has no native timezone-aware type:
a datetime written as tz-aware comes back naive. Comparing a naive value from the
database with a tz-aware `datetime.now(UTC)` raises TypeError at runtime — defect
D-01 in docs/09-test-report.md. Every datetime leaving the persistence layer goes
through `ensure_utc`.
"""

from __future__ import annotations

from collections.abc import Iterator
from datetime import UTC, datetime

from sqlalchemy import create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from .config import settings


class Base(DeclarativeBase):
    pass


def _make_engine(url: str) -> Engine:
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args, future=True)


engine = _make_engine(settings.database_url)
SessionLocal = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False, future=True)


@event.listens_for(Engine, "connect")
def _enable_sqlite_foreign_keys(dbapi_connection, connection_record) -> None:  # noqa: ANN001
    """SQLite ignores FOREIGN KEY clauses unless this pragma is set per connection.

    Without it the ON DELETE CASCADE / SET NULL behaviour documented in
    docs/04-database-design.md silently does nothing.
    """
    if type(dbapi_connection).__module__.startswith("sqlite3"):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()


def utcnow() -> datetime:
    """Single source of 'now' for the I/O layers. Rules never call this."""
    return datetime.now(UTC)


def ensure_utc(value: datetime | None) -> datetime | None:
    """Attach UTC to a naive datetime; convert an aware one to UTC."""
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def init_db() -> None:
    from . import models  # noqa: F401  (import registers the mappers)

    Base.metadata.create_all(bind=engine)


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session that is always closed."""
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()
