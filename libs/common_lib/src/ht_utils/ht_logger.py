import logging
import os

import structlog

from ht_utils.ht_env_config import HtEnvConfig


class HtLogger(structlog.PrintLogger):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__()


class HtLoggerFactory(structlog.PrintLoggerFactory):
    def __call__(self, name: str) -> HtLogger:
        return HtLogger(name)


_LOG_LEVEL = logging.getLevelNamesMapping()[HtEnvConfig().log_level.upper()]

if os.environ.get("PYTEST_VERSION") is None:
    # only configure logger caching when not under test -- would break log
    # capture in testing & test isolation
    structlog.configure(cache_logger_on_first_use=True)

structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.dict_tracebacks,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=HtLoggerFactory(),
    wrapper_class=structlog.make_filtering_bound_logger(_LOG_LEVEL),
)


def get_ht_logger(name: str = __name__) -> structlog.stdlib.BoundLogger:
    logger = structlog.stdlib.get_logger(name)
    return logger
