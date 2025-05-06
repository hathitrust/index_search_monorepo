import inspect
import os
import subprocess
import sys

current = os.path.dirname(os.path.abspath(inspect.getfile(inspect.currentframe())))
parent = os.path.dirname(current)
sys.path.insert(0, parent)

from pathlib import Path

from ht_document.ht_document import HtDocument
from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


def download_document_file(
        ht_id: str = None, target_path: str = None, extension: str = "zip"
):
    os.environ["SDR_DIR"] = '/sdr1/obj'

    ht_doc = HtDocument(document_id=ht_id, document_repository="pairtree")
    source_path = ht_doc.source_path
    try:
        public_key = os.environ["PUBLIC_KEY"]
    except KeyError:
        print("Please define the environment variable PUBLIC_KEY")
        sys.exit(1)
    try:
        user = os.environ["USER"]
    except KeyError:
        logger.info("Please define the environment variable USER")
        sys.exit(1)
    try:
        host = os.environ["HOST"]
    except KeyError:
        logger.info("Please define the environment variable HOST")
        sys.exit(1)

    # Copy the file from remote path
    command = [
        "scp",
        "-i",
        os.path.expanduser(f"~/.ssh/{public_key}"),
        f"{user}@{host}:{source_path}.{extension}",
        f"{target_path}.{extension}",
    ]
    subprocess.run(command)
    print(f"Download {source_path}.{extension} to {target_path}")


if __name__ == "__main__":
    download_document_file(ht_id="coo1.ark:/13960/t57d3f780", target_path=str(Path(__file__).parents[1]),
                           extension="zip")
