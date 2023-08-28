import logging
import os
import subprocess
import sys

from pypairtree import pairtree

SDR_DIR = "/sdr1"


def download_document_file(
    doc_name: str = None, target_path: str = None, extension: str = "zip"
):
    namespace, obj_id = doc_name.split(".")

    doc_path = pairtree.get_pair_path(obj_id)

    source_path = f"{SDR_DIR}/obj/{namespace}/pairtree_root{doc_path}"

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
        f"{user}@{host}:{source_path}/{obj_id}.{extension}",
        target_path,
    ]
    subprocess.run(command)
    logging.info(f"Download {source_path}/{obj_id}.{extension} to {target_path}")
