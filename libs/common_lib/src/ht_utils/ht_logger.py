import logging

import structlog


class HtLogger(structlog.PrintLogger):
    def __init__(self, name: str) -> None:
        self.name = name
        super().__init__()


class HtLoggerFactory(structlog.PrintLoggerFactory):
    def __call__(self, name: str) -> HtLogger:
        return HtLogger(name)


structlog.configure(
    processors=[
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.StackInfoRenderer(),
        structlog.dev.set_exc_info,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.JSONRenderer(),
    ],
    logger_factory=HtLoggerFactory(),
)


def get_ht_logger(
    name: str = __name__, log_level: int = logging.INFO
) -> structlog.stdlib.BoundLogger:

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    logger = structlog.stdlib.get_logger(name)
    return logger
