import logging
import sys
from typing import Optional

from loguru import logger

from app.core.config import get_settings


class InterceptHandler(logging.Handler):
    def emit(self, record: logging.LogRecord) -> None:  # pragma: no cover - thin adapter
        try:
            level = logger.level(record.levelname).name
        except Exception:
            level = record.levelno

        # Find the caller from where the logging call was made
        depth = 2
        frame = logging.currentframe()
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(level, record.getMessage())


_base_logger: Optional[logger.__class__] = None  # type: ignore


def setup_logging(component: str = "api") -> None:
    settings = get_settings()

    # Intercept stdlib logging
    root = logging.getLogger()
    root.handlers = [InterceptHandler()]
    root.setLevel(0)

    for name in (
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "asyncio",
        "celery",
        "kombu",
        "sqlalchemy",
    ):
        _logger = logging.getLogger(name)
        _logger.handlers = [InterceptHandler()]
        _logger.propagate = True
        _logger.setLevel(0)

    # Configure Loguru to structured JSON logs
    logger.remove()
    logger.add(
        sys.stderr,
        level=(settings.log_level or "INFO").upper(),
        serialize=True,  # JSON-ish structured logs
        enqueue=True,
        backtrace=False,
        diagnose=False,
    )

    # Base context
    global _base_logger
    _base_logger = logger.bind(
        service=settings.app_name,
        env=settings.app_env,
        version=settings.app_version,
        component=component,
    )


def get_logger(name: str):
    global _base_logger
    if _base_logger is None:
        setup_logging()
    # Bind a logical logger name without conflicting with record.name
    return _base_logger.bind(logger=name)
