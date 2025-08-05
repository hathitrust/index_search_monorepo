import os
import sys
import csv
import json
import tempfile
import arrow

from typing import Iterable, Sequence, Any
from pathlib import Path
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)

def get_solr_url():
    # Get Solr URL
    try:
        solr_url = os.getenv("SOLR_URL")
        # TODO Remove the line below once SolrExporter been updated self.solr_url = f"{solr_url}/query"
        return solr_url.strip('/')
    except AttributeError:
        logger.error("Error: `SOLR_URL` environment variable required")
        sys.exit(1)

def get_current_time(current=None, str_format: str = "YYYY-MM-DD HH:mm:ss"):
    """
    Returns the current time in the format HH:MM:SS.
    :param current: The current time
    :param str_format: The format of the time to return
    """
    if current is None:
        current = arrow.now()

    return str(current.format(str_format))


def get_general_error_message(service_name: str, e: Exception) -> dict:
    """
    Returns an error dictionary with information about the cause of the error
    :param service_name: The name of the service that raised the error
    :param e: The exception
    """

    return {'service_name': service_name,
            'error_message': e,
            'timestamp': get_current_time()
            }


def get_error_message_by_document(service_name: str, e: Exception, doc: dict) -> dict:
    """
    Returns an error dictionary with information about
    a specific document and the cause of the error

    :param service_name: The name of the service that raised the error
    :param e: The exception
    :param doc: The document, the document is a dictionary that
     must have a key 'ht_id'
    """

    # TODO Check if in the future we want to add more information about the document, like the record_id or probably
    # the full message received from the queue or the full document

    return {'service_name': service_name,
            'error_message': e,
            'ht_id': doc.get('ht_id') if doc.get('ht_id') else doc.get('id'),
            'timestamp': get_current_time()
            }

def split_into_batches(documents, batch_size):
    """Split the list of documents into batches of given size."""
    for i in range(0, len(documents), batch_size):
        yield documents[i:i + batch_size]

def comma_separated_list(arg):
    return arg.split(",")

def find_sdr1_obj():
    root = Path("/")  # root of the container
    candidate = root / "sdr1" / "obj"
    if candidate.exists():
        return candidate
    else:
        raise FileNotFoundError("Folder '/sdr1/obj' not found in the container root")


def write_csv_and_get_path(
        rows: Iterable[Any],                 # rows can be dicts or JSON strings
        required_fields: Sequence[str] | None = None,
        out_dir: str | Path | None = None,
        filename: str = "export.csv",
) -> dict:
    """
    Write ONLY the required fields to a CSV on disk and return path + meta.
    """
    if required_fields is None:
        required_fields = ("id",)        # safe default

    # ts = datetime.now().strftime("%Y%m%d-%H%M%S")
    # stem, ext = os.path.splitext(filename)
    # filename_ts = f"{stem}_{ts}{ext or '.csv'}"
    filename_ts = filename
    out_dir = Path(out_dir or tempfile.gettempdir())
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / filename_ts

    total = 0
    with path.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=required_fields, extrasaction="ignore")
        writer.writeheader()

        for row in rows:
            # Normalize to dict
            if isinstance(row, (bytes, bytearray)):
                row = row.decode()
            if isinstance(row, str):
                row = json.loads(row)

            # Keep only required fields (fill missing with "")
            filtered = {k: row.get(k, "") for k in required_fields}
            writer.writerow(filtered)
            total += 1

    return {
        "file_path": str(path),
        "total_records": total,
    }