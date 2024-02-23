import os
import subprocess
import sys

from ht_utils.ht_logger import get_ht_logger

logger = get_ht_logger(name=__name__)


def download_document_file(
        source_path: str = None, target_path: str = None, extension: str = "zip"
):
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
    logger.info(f"Download {source_path}.{extension} to {target_path}")
