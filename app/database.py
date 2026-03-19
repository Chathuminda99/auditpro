import logging
import time

from sqlalchemy import create_engine
from sqlalchemy import event
from sqlalchemy.orm import sessionmaker, Session

from app.config import get_settings


settings = get_settings()
DB_LOGGER = logging.getLogger("auditpro.db")


def _compact_sql(statement: str | None) -> str:
    if not statement:
        return "-"
    return " ".join(statement.split())

engine = create_engine(
    settings.database_url,
    echo=False,
    pool_pre_ping=True,
)


@event.listens_for(engine, "before_cursor_execute")
def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Store query start time for duration logging."""
    conn.info.setdefault("query_start_time", []).append(time.perf_counter())


@event.listens_for(engine, "after_cursor_execute")
def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
    """Log slow queries and optionally all queries."""
    started_times = conn.info.get("query_start_time", [])
    if not started_times:
        return

    started_at = started_times.pop(-1)
    duration_ms = (time.perf_counter() - started_at) * 1000

    if not settings.db_log_queries and duration_ms < settings.db_slow_query_ms:
        return

    event_name = "slow_query" if duration_ms >= settings.db_slow_query_ms else "query"
    DB_LOGGER.info(
        "%s duration_ms=%.2f rowcount=%s executemany=%s sql=%s",
        event_name,
        duration_ms,
        cursor.rowcount,
        executemany,
        _compact_sql(statement),
    )


@event.listens_for(engine, "handle_error")
def handle_db_error(exception_context):
    """Emit DB failures to the dedicated database log."""
    started_times = exception_context.connection.info.get("query_start_time", [])
    if started_times:
        started_times.pop(-1)

    DB_LOGGER.error(
        "db_error error=%s sql=%s",
        exception_context.original_exception,
        _compact_sql(exception_context.statement),
    )


SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db() -> Session:
    """Dependency to get a database session."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
