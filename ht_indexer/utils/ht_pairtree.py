import logging
import os
import subprocess
import sys


def download_document_file(
        source_path: str = None, target_path: str = None, extension: str = "zip"
):
    try:
        public_key = os.environ["PUBLIC_KEY"]
    except KeyError:
        print(f"Please define the environment variable PUBLIC_KEY")
        sys.exit(1)
    try:
        user = os.environ["USER"]
    except KeyError:
        logging.info(f"Please define the environment variable USER")
        sys.exit(1)
    try:
        host = os.environ["HOST"]
    except KeyError:
        logging.info(f"Please define the environment variable HOST")
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
    logging.info(f"Download {source_path}.{extension} to {target_path}")
