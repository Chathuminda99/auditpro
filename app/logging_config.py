"""Centralized application logging configuration."""

from __future__ import annotations

import logging
from contextvars import ContextVar
from logging.handlers import RotatingFileHandler
from pathlib import Path


DEFAULT_LOG_CONTEXT = {
    "request_id": "-",
    "user_id": "-",
    "tenant_id": "-",
    "client_ip": "-",
    "method": "-",
    "path": "-",
}

_log_context: ContextVar[dict[str, str]] = ContextVar(
    "auditpro_log_context",
    default=DEFAULT_LOG_CONTEXT.copy(),
)
_logging_configured = False


def _normalize_context_value(value: object | None) -> str:
    if value is None:
        return "-"
    text = str(value).strip()
    return text or "-"


def reset_log_context() -> None:
    """Clear per-request logging context."""
    _log_context.set(DEFAULT_LOG_CONTEXT.copy())


def bind_log_context(**kwargs: object) -> None:
    """Update the current request logging context."""
    context = DEFAULT_LOG_CONTEXT.copy()
    context.update(_log_context.get())
    for key, value in kwargs.items():
        if key in DEFAULT_LOG_CONTEXT:
            context[key] = _normalize_context_value(value)
    _log_context.set(context)


class RequestContextFilter(logging.Filter):
    """Inject request-scoped metadata into every log record."""

    def filter(self, record: logging.LogRecord) -> bool:
        context = DEFAULT_LOG_CONTEXT.copy()
        context.update(_log_context.get())
        for key, value in context.items():
            setattr(record, key, value)
        return True


def _reset_logger(
    name: str,
    level: int,
    handlers: list[logging.Handler],
    *,
    propagate: bool = False,
) -> logging.Logger:
    logger = logging.getLogger(name)
    logger.handlers.clear()
    logger.setLevel(level)
    logger.propagate = propagate
    for handler in handlers:
        logger.addHandler(handler)
    return logger


def configure_logging(settings) -> None:
    """Configure console and rotating file logging for the app."""
    global _logging_configured
    if _logging_configured:
        return

    log_dir = Path(settings.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    context_filter = RequestContextFilter()
    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "req=%(request_id)s user=%(user_id)s tenant=%(tenant_id)s "
        "ip=%(client_ip)s %(method)s %(path)s | %(message)s",
        "%Y-%m-%d %H:%M:%S",
    )
    console_formatter = logging.Formatter(
        "%(asctime)s | %(levelname)-8s | %(name)s | "
        "req=%(request_id)s %(method)s %(path)s | %(message)s",
        "%H:%M:%S",
    )

    def build_handler(filename: str, *, level: int, console: bool = False) -> logging.Handler:
        if console:
            handler: logging.Handler = logging.StreamHandler()
            handler.setFormatter(console_formatter)
        else:
            handler = RotatingFileHandler(
                log_dir / filename,
                maxBytes=settings.log_max_bytes,
                backupCount=settings.log_backup_count,
                encoding="utf-8",
            )
            handler.setFormatter(formatter)
        handler.setLevel(level)
        handler.addFilter(context_filter)
        return handler

    resolved_level = getattr(logging, str(settings.log_level).upper(), logging.INFO)
    console_handler = build_handler("console.log", level=resolved_level, console=True)
    server_handler = build_handler("server.log", level=resolved_level)
    access_handler = build_handler("access.log", level=logging.INFO)
    app_handler = build_handler("app.log", level=resolved_level)
    db_handler = build_handler("db.log", level=logging.INFO)
    security_handler = build_handler("security.log", level=logging.INFO)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.setLevel(logging.WARNING)
    root_logger.addHandler(console_handler)

    _reset_logger(
        "auditpro.app",
        resolved_level,
        [console_handler, app_handler],
    )
    _reset_logger(
        "auditpro.access",
        logging.INFO,
        [console_handler, access_handler],
    )
    _reset_logger(
        "auditpro.db",
        logging.INFO,
        [db_handler],
    )
    _reset_logger(
        "auditpro.security",
        logging.INFO,
        [console_handler, security_handler],
    )
    _reset_logger(
        "uvicorn.error",
        resolved_level,
        [console_handler, server_handler],
    )
    _reset_logger(
        "uvicorn.access",
        logging.WARNING,
        [access_handler],
    )
    _reset_logger(
        "sqlalchemy.engine",
        logging.INFO if settings.db_log_queries else logging.WARNING,
        [db_handler],
    )
    _reset_logger(
        "sqlalchemy.pool",
        logging.WARNING,
        [db_handler],
    )

    _logging_configured = True
