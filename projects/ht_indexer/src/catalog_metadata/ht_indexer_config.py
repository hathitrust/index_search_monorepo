import os
from pathlib import Path

from ht_utils.ht_utils import find_sdr1_obj

MAX_ITEM_IDS = 1000

MYQLS_METADATA = ["coll_id", "ht_heldby", "ht_heldby_brlm", "rights"]

DOCUMENT_LOCAL_PATH = "/tmp/"

# Look for the sdr1 obj folder in the root of the container
# and if it is not found, use the default path
def get_local_document_folder():
    """
    Returns the local document folder
    :return: str
    """

    try:
        local_document_folder = find_sdr1_obj()
        return local_document_folder
    except FileNotFoundError:
        local_document_folder = f"{Path(__file__).parents[1]}/sdr1/obj"
        return local_document_folder


# field_full_text : field catalog
RENAMED_CATALOG_METADATA = {
    "record_no": "id",
    "date": "publishDate",
    "Vauthor": "author",
    "Vtitle": "title",
}

IDENTICAL_CATALOG_METADATA = [
    "author",
    "author2",
    "lccn",
    "sdrnum",
    "rptnum",
    "oclc",
    "issn",
    "isbn",
    "edition",
    # "ht_id_display",  # Appear in full-text search schema do we want to keep it?
    "isn_related",
    "callnumber",
    "sudoc",
    "language",
    "language008_full",
    "format",
    "htsource",
    "publisher",
    # 'Vauthor', # eq to author
    # ====Check author fields====
    "author_top",
    "author_rest",
    "authorSort",
    "author_sortkey",
    "mainauthor",  # This is an optional field
    # ============================
    # ====Check title fields====
    "vtitle",
    "title_c",
    "title_sortkey",
    "title_display",
    "title",
    "titleSort",
    # 'Vtitle', is title in Catalog
    "title_ab",
    "title_a",
    "title_top",
    "title_rest",
    # ============================
    # 'volume_enumcron', field obtain using the field ht_id_display
    "series",
    "series2",
    "serialTitle_ab",
    "serialTitle_a",
    "serialTitle",
    "serialTitle_rest",
    "topicStr",
    "publishDate",
    "geographicStr",
    "countryOfPubStr",
    "genre",
    "era",
    "fullrecord"
]

# indexer queue
queue_host = os.getenv("QUEUE_HOST") if os.getenv("QUEUE_HOST") else "localhost"
indexer_queue_name = "indexer_queue"

# False means that the message will be discarded from the queue and for our service they will be published
# in a dead letter queue
indexer_requeue_message = False
# Default batch size for the indexer service determined running experiments on the indexer
# service in the docker container
indexer_batch_size = 100

