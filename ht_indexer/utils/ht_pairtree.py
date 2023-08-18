import logging
import subprocess
import os
from pypairtree import pairtree


# TODO: Define environment variables instead of global variables
HOST = 'dev-2.babel.hathitrust.org'
USER = 'lisepul'
PUBLIC_KEY = 'lisepul-dev-2_babel_server'
SDR_DIR = '/sdr1'

def download_document_file(doc_name: str = None, target_path: str = None):

    namespace, obj_id = doc_name.split(".")

    doc_path = pairtree.get_pair_path(obj_id)

    source_path = f'{SDR_DIR}/obj/{namespace}/pairtree_root{doc_path}'

    # Copy the file to the remote path
    for extension in ['zip','mets.xml']:
        command = ["scp",
                   "-i",
                   os.path.expanduser(f'~/.ssh/{PUBLIC_KEY}'),
                   f"{USER}@{HOST}:{source_path}/{obj_id}.{extension}", target_path]
        subprocess.run(command)
        logging.info(f"Download {source_path}/{obj_id}.{extension} to {target_path}")