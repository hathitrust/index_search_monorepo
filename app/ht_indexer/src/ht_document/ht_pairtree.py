import inspect
import os
import subprocess
import sys
from pathlib import Path

from ht_utils.ht_logger import get_ht_logger

from ht_document.ht_document import HtDocument

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

logger = get_ht_logger(name=__name__)


def download_document_file(ht_id: str, target_path: str, extension: str = "zip"):
    os.environ.setdefault("SDR_DIR", "/sdr1/obj")

    required_env = ["PUBLIC_KEY", "USER", "HOST"]
    missing_vars = [var for var in required_env if var not in os.environ]
    if missing_vars:
        raise OSError(f"Missing environment variables: {', '.join(missing_vars)}")

    public_key = os.environ["PUBLIC_KEY"]
    user = os.environ["USER"]
    host = os.environ["HOST"]

    ht_doc = HtDocument(document_id=ht_id, document_repository="pairtree")
    source_path = ht_doc.source_path

    command = [
        "scp",
        "-i",
        os.path.expanduser(f"~/.ssh/{public_key}"),
        f"{user}@{host}:{source_path}.{extension}",
        f"{target_path}.{extension}",
    ]

    try:
        subprocess.run(command, check=True)
        logger.info(f"Downloaded {source_path}.{extension} to {target_path}")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to download file: {e}")
        raise

    # Copy the file from remote path
    command = [
        "scp",
        "-i",
        os.path.expanduser(f"~/.ssh/{public_key}"),
        f"{user}@{host}:{source_path}.{extension}",
        f"{target_path}.{extension}",
    ]
    subprocess.run(command)
    logger.error(f"Download {source_path}.{extension} to {target_path}")


if __name__ == "__main__":
    download_document_file(ht_id="coo1.ark:/13960/t57d3f780", target_path=str(Path(__file__).parents[1]),
                           extension="zip")
