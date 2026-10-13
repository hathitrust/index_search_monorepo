import logging
from typing import Any

import structlog

structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
            ],
        )



def get_ht_logger(name: str = __name__, log_level: int | str = logging.INFO) -> structlog.stdlib.BoundLogger:
#    print(f"GET YE LOGGER {name} 🪵")

    structlog.configure(
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
    )

    return structlog.stdlib.get_logger().bind(name=name)
