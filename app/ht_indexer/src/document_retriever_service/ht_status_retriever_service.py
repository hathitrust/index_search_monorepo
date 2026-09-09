from pathlib import Path

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


def get_non_processed_ids(
    status_file: str | Path, list_ids: list[str]
) -> tuple[list[str], list[str]]:
    try:
        with open(status_file) as f:
            processed_ids = f.read().splitlines()
    except FileNotFoundError:
        logger.info(f"Status file {status_file} not found. Assuming no IDs processed yet.")
        processed_ids = []

    logger.info(f"Total of items have been processed before {len(processed_ids)}")
    items2process = list(set(list_ids) - set(processed_ids))
    return items2process, processed_ids
